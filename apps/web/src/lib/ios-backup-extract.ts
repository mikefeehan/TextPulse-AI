/**
 * Client-side iTunes/Finder backup extraction.
 *
 * Users who want to import iMessage history from a multi-GB iPhone backup
 * cannot upload the whole backup folder to TextPulse — uploads would be
 * 5–50 GB and wall-clock hours. They do not need to. Only Messages lives in
 * `chat.db`, typically well under a gigabyte, and the backup's Manifest.db
 * index tells us exactly which hashed blob in the backup is that file.
 *
 * This module does the whole lookup entirely in the browser:
 *
 *   1. User picks the iPhone backup folder via `<input webkitdirectory>`.
 *      Browsers expose each file as a `File` handle to disk — none of the
 *      bytes are read until we ask for them.
 *   2. We read ONE file from the folder: `Manifest.db`, a few MB of SQLite.
 *   3. We load sql.js (WASM SQLite) on demand and query Manifest.db for the
 *      fileID of `HomeDomain/Library/SMS/sms.db`.
 *   4. We find the matching hashed blob inside the backup folder and return
 *      it as a freshly-named `File` the existing upload flow can send.
 *
 * Nothing but Manifest.db + the chat.db blob is ever read or uploaded.
 */

import type { Database, SqlJsStatic } from "sql.js";

export type ExtractionPhase =
  | "locating-manifest"
  | "reading-manifest"
  | "loading-sqlite"
  | "querying-manifest"
  | "locating-chat-db"
  | "done";

export interface ExtractionProgress {
  phase: ExtractionPhase;
  deviceName?: string | null;
  chatDbBytes?: number;
  detail?: string;
}

export interface ExtractedChatDb {
  file: File;
  deviceName: string | null;
  byteLength: number;
}

export class IOSBackupExtractionError extends Error {
  constructor(message: string, readonly userFacing: string = message) {
    super(message);
    this.name = "IOSBackupExtractionError";
  }
}

export class IOSBackupEncryptedError extends IOSBackupExtractionError {
  constructor() {
    super(
      "Backup is encrypted",
      "This iPhone backup is encrypted, so TextPulse cannot read the Messages database. In iTunes, uncheck 'Encrypt local backup', create a fresh backup, and try again."
    );
    this.name = "IOSBackupEncryptedError";
  }
}

const IMESSAGE_DOMAIN = "HomeDomain";
const IMESSAGE_RELATIVE_PATH = "Library/SMS/sms.db";
const SQLITE_MAGIC = new TextEncoder().encode("SQLite format 3\u0000");

let sqlJsPromise: Promise<SqlJsStatic> | null = null;

async function loadSqlJs(): Promise<SqlJsStatic> {
  if (!sqlJsPromise) {
    sqlJsPromise = (async () => {
      const mod = await import("sql.js");
      const initSqlJs = (mod.default ?? (mod as unknown as typeof mod.default)) as (
        config?: Parameters<typeof mod.default>[0]
      ) => Promise<SqlJsStatic>;
      return initSqlJs({
        // Served from apps/web/public/sql-wasm.wasm
        locateFile: (file: string) => `/${file}`,
      });
    })();
  }
  return sqlJsPromise;
}

/**
 * Locate and extract chat.db from a user-picked iTunes/Finder backup folder.
 *
 * `files` is the `FileList` (or any File iterable) that the browser hands
 * back from an `<input type="file" webkitdirectory>` selection.
 */
export async function extractChatDbFromBackupFolder(
  files: ArrayLike<File> | Iterable<File>,
  onProgress: (progress: ExtractionProgress) => void = () => {}
): Promise<ExtractedChatDb> {
  const fileList = Array.from(files as Iterable<File>);
  if (fileList.length === 0) {
    throw new IOSBackupExtractionError(
      "No files selected",
      "No files were selected. Pick the iPhone backup folder that holds Manifest.db."
    );
  }

  onProgress({ phase: "locating-manifest" });

  // Index the folder contents by their relative path so we can O(1) look up
  // the manifest and the chat.db blob later.
  const byRelativePath = new Map<string, File>();
  for (const file of fileList) {
    const relative = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
    byRelativePath.set(relative, file);
  }

  const manifestEntry = findManifestEntry(byRelativePath);
  if (!manifestEntry) {
    throw new IOSBackupExtractionError(
      "Manifest.db not found",
      "This folder does not look like an iPhone backup. Pick the device folder inside %APPDATA%\\Apple\\MobileSync\\Backup — it must contain Manifest.db."
    );
  }

  onProgress({ phase: "reading-manifest", detail: `${formatBytes(manifestEntry.file.size)}` });
  const manifestBytes = new Uint8Array(await manifestEntry.file.arrayBuffer());
  ensureSqliteMagic(manifestBytes);

  onProgress({ phase: "loading-sqlite" });
  const SQL = await loadSqlJs();

  onProgress({ phase: "querying-manifest" });
  const db: Database = new SQL.Database(manifestBytes);
  let chatDbHash: string | null = null;
  try {
    const statement = db.prepare(
      "SELECT fileID FROM Files WHERE domain = :domain AND relativePath = :relativePath"
    );
    statement.bind({ ":domain": IMESSAGE_DOMAIN, ":relativePath": IMESSAGE_RELATIVE_PATH });
    if (statement.step()) {
      const row = statement.get();
      chatDbHash = typeof row[0] === "string" ? row[0] : null;
    }
    statement.free();
  } finally {
    db.close();
  }

  if (!chatDbHash) {
    throw new IOSBackupExtractionError(
      "chat.db missing from backup",
      "This backup does not contain the Messages database. Make sure Messages were included when iTunes made the backup."
    );
  }

  onProgress({ phase: "locating-chat-db" });
  const blobRelativePath = `${manifestEntry.rootPrefix}${chatDbHash.slice(0, 2)}/${chatDbHash}`;
  const blobFile =
    byRelativePath.get(blobRelativePath) ??
    // Some older backups store blobs flat at the root.
    byRelativePath.get(`${manifestEntry.rootPrefix}${chatDbHash}`);
  if (!blobFile) {
    throw new IOSBackupExtractionError(
      "chat.db blob missing",
      "The backup references a Messages database that is not on disk. The backup may be incomplete — make a fresh backup in iTunes and try again."
    );
  }

  const deviceName = await tryReadDeviceName(byRelativePath, manifestEntry.rootPrefix);

  // Wrap the blob with a friendly filename so downstream logs and preview
  // records say "chat.db" instead of a 40-char hash.
  const chatDbFile = new File([blobFile], "chat.db", {
    type: "application/x-sqlite3",
    lastModified: blobFile.lastModified,
  });

  onProgress({
    phase: "done",
    deviceName,
    chatDbBytes: chatDbFile.size,
  });

  return {
    file: chatDbFile,
    deviceName,
    byteLength: chatDbFile.size,
  };
}

interface ManifestLocation {
  file: File;
  /** Prefix every file in this backup shares, ending with "/". Empty if none. */
  rootPrefix: string;
}

function findManifestEntry(byRelativePath: Map<string, File>): ManifestLocation | null {
  // Prefer the shallowest Manifest.db so a stray nested SQLite with the same
  // name can't confuse us.
  let best: ManifestLocation | null = null;
  let bestDepth = Infinity;
  for (const [relative, file] of byRelativePath) {
    if (!relative.endsWith("Manifest.db")) continue;
    const segment = "Manifest.db";
    const isExact = relative === segment;
    const prefix = isExact ? "" : relative.slice(0, relative.length - segment.length);
    // Prefix should end in "/" if not empty.
    if (prefix.length > 0 && !prefix.endsWith("/")) continue;
    const depth = prefix.split("/").filter(Boolean).length;
    if (depth < bestDepth) {
      best = { file, rootPrefix: prefix };
      bestDepth = depth;
    }
  }
  return best;
}

function ensureSqliteMagic(bytes: Uint8Array): void {
  if (bytes.length < SQLITE_MAGIC.length) {
    throw new IOSBackupEncryptedError();
  }
  for (let i = 0; i < SQLITE_MAGIC.length; i += 1) {
    if (bytes[i] !== SQLITE_MAGIC[i]) {
      throw new IOSBackupEncryptedError();
    }
  }
}

async function tryReadDeviceName(
  byRelativePath: Map<string, File>,
  rootPrefix: string
): Promise<string | null> {
  const infoFile = byRelativePath.get(`${rootPrefix}Info.plist`);
  if (!infoFile) return null;
  try {
    const text = await infoFile.text();
    // Info.plist is XML in iTunes backups. A tolerant regex is good enough to
    // surface a friendly device name for display, and failing quietly is fine.
    const match =
      text.match(/<key>Device Name<\/key>\s*<string>([^<]*)<\/string>/) ??
      text.match(/<key>Display Name<\/key>\s*<string>([^<]*)<\/string>/);
    return match ? match[1] : null;
  } catch {
    return null;
  }
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}
