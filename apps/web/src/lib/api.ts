import {
  AuthResponse,
  ContactDetail,
  ContactListItem,
  ContactSummary,
  ImportInstruction,
  ImportPreviewResponse,
  ImportStatusResponse,
  ImportUploadResponse,
  QAReply,
  QASession,
  ReplyCoachResponse,
  User,
  VaultCategoryDetail,
  VaultCategoryRead,
} from "@/lib/types";
import {
  demoContactDetails,
  demoContacts,
  demoInstructions,
  demoQaSession,
  demoUser,
  demoVaultCategories,
  demoVaultDetails,
} from "@/lib/demo-data";
import {
  appendDemoQaMessages,
  createDemoQaReply,
  createDemoReplyCoach,
} from "@/lib/mock-engine";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "";

type ContactCreatePayload = {
  name: string;
  relationship_type: ContactSummary["relationship_type"];
  is_dating_mode: boolean;
  photo_url?: string | null;
};

type DemoState = {
  sessions: Record<string, QASession[]>;
  contacts: ContactListItem[];
  details: Record<string, ContactDetail>;
};

const demoState: DemoState = {
  sessions: {
    "c-ava": [demoQaSession],
    "c-daniel": [
      {
        ...demoQaSession,
        id: "qa-2",
        messages: [
          {
            id: "qa-3",
            role: "user",
            content: "How should I push back without sounding sharp?",
            created_at: new Date().toISOString(),
          },
          {
            id: "qa-4",
            role: "assistant",
            content:
              "Lead with the operational issue first and the emotional impact second. Daniel tends to respond well to clarity and low-drama directness.",
            created_at: new Date().toISOString(),
          },
        ],
      },
    ],
  },
  contacts: [...demoContacts],
  details: structuredClone(demoContactDetails),
};

function isBrowser() {
  return typeof window !== "undefined";
}

export function hasLiveApi() {
  return Boolean(API_BASE_URL);
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  token?: string | null,
): Promise<T> {
  if (!API_BASE_URL) {
    throw new Error("Demo mode");
  }

  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (!(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed (${response.status})`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  try {
    return await request<AuthResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  } catch {
    return {
      access_token: "demo-token",
      token_type: "bearer",
      user: { ...demoUser, email },
    };
  }
}

export async function signup(email: string, password: string): Promise<AuthResponse> {
  try {
    return await request<AuthResponse>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  } catch {
    return {
      access_token: "demo-token",
      token_type: "bearer",
      user: { ...demoUser, email },
    };
  }
}

export async function me(token: string): Promise<User> {
  try {
    return await request<User>("/api/auth/me", {}, token);
  } catch {
    return demoUser;
  }
}

export async function listContacts(token: string): Promise<ContactListItem[]> {
  try {
    return await request<ContactListItem[]>("/api/contacts", {}, token);
  } catch {
    return demoState.contacts;
  }
}

export async function createContact(
  token: string,
  payload: ContactCreatePayload,
): Promise<ContactSummary> {
  try {
    return await request<ContactSummary>("/api/contacts", {
      method: "POST",
      body: JSON.stringify(payload),
    }, token);
  } catch {
    const id = `demo-${Date.now()}`;
    const createdAt = new Date().toISOString();
    const summary: ContactSummary = {
      id,
      name: payload.name,
      relationship_type: payload.relationship_type,
      is_dating_mode: payload.is_dating_mode,
      photo_url: payload.photo_url ?? null,
      profile_generated_at: createdAt,
      created_at: createdAt,
      updated_at: createdAt,
    };
    demoState.contacts.unshift({
      ...summary,
      latest_message_at: null,
      message_count: 0,
      import_count: 0,
      top_takeaway: "Fresh contact created. Import messages to generate a profile.",
    });
    demoState.details[id] = {
      ...demoContactDetails["c-ava"],
      ...summary,
      profile: {
        ...demoContactDetails["c-ava"].profile!,
        key_takeaways: [
          {
            title: "Fresh Contact",
            detail: "Import a conversation to replace this starter profile with a real analysis.",
          },
        ],
      },
      imports: [],
      recent_messages: [],
    };
    return summary;
  }
}

export async function getContact(
  token: string,
  contactId: string,
): Promise<ContactDetail> {
  try {
    return await request<ContactDetail>(`/api/contacts/${contactId}`, {}, token);
  } catch {
    return demoState.details[contactId] ?? demoState.details["c-ava"];
  }
}

export async function listImportInstructions(): Promise<ImportInstruction[]> {
  try {
    return await request<ImportInstruction[]>("/api/contacts/import-instructions");
  } catch {
    return demoInstructions;
  }
}

export async function listVaultCategories(
  token: string,
  contactId: string,
): Promise<VaultCategoryRead[]> {
  try {
    return await request<VaultCategoryRead[]>(
      `/api/contacts/${contactId}/vault/categories`,
      {},
      token,
    );
  } catch {
    return demoVaultCategories;
  }
}

export async function getVaultCategory(
  token: string,
  contactId: string,
  categoryId: string,
): Promise<VaultCategoryDetail> {
  try {
    return await request<VaultCategoryDetail>(
      `/api/contacts/${contactId}/vault/categories/${categoryId}`,
      {},
      token,
    );
  } catch {
    return demoVaultDetails[categoryId] ?? demoVaultDetails["cat-flirty"];
  }
}

export async function listQaSessions(
  token: string,
  contactId: string,
): Promise<QASession[]> {
  try {
    return await request<QASession[]>(`/api/contacts/${contactId}/qa/sessions`, {}, token);
  } catch {
    return demoState.sessions[contactId] ?? [demoQaSession];
  }
}

export async function createQaSession(
  token: string,
  contactId: string,
): Promise<QASession> {
  try {
    const response = await request<{ session: QASession }>(
      `/api/contacts/${contactId}/qa/sessions`,
      { method: "POST" },
      token,
    );
    return response.session;
  } catch {
    const session: QASession = {
      id: `demo-session-${Date.now()}`,
      created_at: new Date().toISOString(),
      messages: [],
    };
    demoState.sessions[contactId] = [session, ...(demoState.sessions[contactId] ?? [])];
    return session;
  }
}

export async function sendQaMessage(
  token: string,
  contactId: string,
  sessionId: string,
  content: string,
): Promise<QAReply> {
  try {
    return await request<QAReply>(
      `/api/contacts/${contactId}/qa/sessions/${sessionId}/messages`,
      {
        method: "POST",
        body: JSON.stringify({ content }),
      },
      token,
    );
  } catch {
    const contact = demoState.details[contactId] ?? demoState.details["c-ava"];
    const session =
      (demoState.sessions[contactId] ?? []).find((item) => item.id === sessionId) ??
      demoQaSession;
    const reply = createDemoQaReply(contact, content, session);
    const updated = appendDemoQaMessages(session, content, reply);
    demoState.sessions[contactId] = (demoState.sessions[contactId] ?? []).map((item) =>
      item.id === sessionId ? updated : item,
    );
    return reply;
  }
}

export async function coachReply(
  token: string,
  contactId: string,
  incomingMessage: string,
): Promise<ReplyCoachResponse> {
  try {
    return await request<ReplyCoachResponse>(
      `/api/contacts/${contactId}/reply-coach`,
      {
        method: "POST",
        body: JSON.stringify({ incoming_message: incomingMessage }),
      },
      token,
    );
  } catch {
    const detail = demoState.details[contactId] ?? demoState.details["c-ava"];
    return createDemoReplyCoach(detail, incomingMessage);
  }
}

export async function regenerateAnalysis(
  token: string,
  contactId: string,
): Promise<{ status: string; message: string }> {
  try {
    return await request<{ status: string; message: string }>(
      `/api/contacts/${contactId}/analysis/regenerate`,
      { method: "POST" },
      token,
    );
  } catch {
    return { status: "completed", message: "Demo mode." };
  }
}

export async function getAnalysisStatus(
  token: string,
  contactId: string,
): Promise<{ status: string; error: string | null; has_profile: boolean; profile_generated_at: string | null }> {
  return request(
    `/api/contacts/${contactId}/analysis/status`,
    {},
    token,
  );
}

export interface ScanResult {
  message_count: number;
  contact_message_count: number;
  user_message_count: number;
  tier: { name: string; label: string; max_messages: number; price_usd: number };
  date_range: { start: string | null; end: string | null };
  duration_days: number;
  top_topics: string[];
  moments: string[];
  behavioral_snapshot: {
    investment_asymmetry: number;
    investment_verdict: string;
    ghost_risk: number;
    ghost_risk_factors: string[];
    fade_detected: boolean;
    fade_signals: string[];
    worth_your_time: string;
    messages_per_active_day: number;
    contact_initiation_rate: number;
    length_asymmetry: number;
  };
}

export async function scanAnalysis(
  token: string,
  contactId: string,
): Promise<ScanResult> {
  return request<ScanResult>(
    `/api/contacts/${contactId}/analysis/scan`,
    {},
    token,
  );
}

export async function createCheckoutSession(
  token: string,
  contactId: string,
): Promise<{ checkout_url: string; tier: { name: string; label: string; price_usd: number } }> {
  return request(
    `/api/contacts/${contactId}/analysis/checkout`,
    { method: "POST" },
    token,
  );
}

export async function createPasteImport(
  token: string,
  contactId: string,
  content: string,
): Promise<ImportUploadResponse> {
  try {
    return await request(
      `/api/contacts/${contactId}/imports/paste`,
      {
        method: "POST",
        body: JSON.stringify({
          source_platform: "paste",
          file_name: "pasted-conversation.txt",
          content,
          run_analysis: true,
        }),
      },
      token,
    );
  } catch {
    return {
      import_id: `demo-import-${Date.now()}`,
      status: "completed",
      message_count: content.split("\n").filter(Boolean).length,
      profile_refreshed: true,
      queued: false,
      import_record: null,
    };
  }
}

export async function uploadImport(
  token: string,
  contactId: string,
  file: File,
  sourcePlatform: string,
  contactIdentifier?: string,
  onProgress?: (progress: number) => void,
): Promise<ImportUploadResponse> {
  if (!API_BASE_URL) {
    return {
      import_id: `demo-upload-${Date.now()}`,
      status: "completed",
      message_count: 42,
      profile_refreshed: true,
      queued: false,
      import_record: null,
    };
  }

  const formData = new FormData();
  formData.append("source_platform", sourcePlatform);
  formData.append("run_analysis", "true");
  if (contactIdentifier) {
    formData.append("contact_identifier", contactIdentifier);
  }
  formData.append("file", file);

  return new Promise<ImportUploadResponse>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/api/contacts/${contactId}/imports/upload`);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
      }
    };
    xhr.onerror = () => {
      reject(new Error("Network error while uploading import."));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as ImportUploadResponse);
        return;
      }
      reject(new Error(xhr.responseText || `Request failed (${xhr.status})`));
    };
    xhr.send(formData);
  });
}

export async function previewImport(
  token: string,
  contactId: string,
  file: File,
  sourcePlatform: string,
  contactIdentifier?: string,
  onProgress?: (progress: number) => void,
): Promise<ImportPreviewResponse> {
  if (!API_BASE_URL) {
    const content = await file.text();
    const lines = content.split(/\r?\n/).filter(Boolean);
    return {
      preview_id: `demo-preview-${Date.now()}`,
      file_name: file.name,
      source_platform: sourcePlatform,
      message_count: lines.length,
      date_range: {
        start: new Date(Date.now() - 1000 * 60 * 60 * 24 * 14).toISOString(),
        end: new Date().toISOString(),
      },
      previews: lines.slice(0, 6).map((line, index) => ({
        canonical_id: `demo-line-${index}`,
        sender: index % 2 === 0 ? "contact" : "user",
        text: line,
        timestamp: new Date(Date.now() - index * 1000 * 60 * 30).toISOString(),
        message_type: "text",
      })),
      stats: {
        user_messages: Math.floor(lines.length / 2),
        contact_messages: Math.ceil(lines.length / 2),
        text_messages: lines.length,
        reaction_messages: 0,
        contact_identifier: contactIdentifier ?? "Unknown",
      },
      selection_required: sourcePlatform === "imessage" && !contactIdentifier,
      contact_options:
        sourcePlatform === "imessage" && !contactIdentifier
          ? [
              {
                identifier: "+15551234567",
                label: "Ava (+1 555-123-4567)",
                total_messages: 8421,
                sent_messages: 4200,
                received_messages: 4221,
                latest_message_at: new Date().toISOString(),
              },
              {
                identifier: "+15557654321",
                label: "Daniel (+1 555-765-4321)",
                total_messages: 3110,
                sent_messages: 1504,
                received_messages: 1606,
                latest_message_at: new Date(Date.now() - 1000 * 60 * 60 * 10).toISOString(),
              },
            ]
          : [],
    };
  }

  const formData = new FormData();
  formData.append("source_platform", sourcePlatform);
  if (contactIdentifier) {
    formData.append("contact_identifier", contactIdentifier);
  }
  formData.append("file", file);

  return new Promise<ImportPreviewResponse>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/api/contacts/${contactId}/imports/preview`);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
      }
    };
    xhr.onerror = () => {
      reject(new Error("Network error while building the import preview."));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as ImportPreviewResponse);
        return;
      }
      reject(new Error(xhr.responseText || `Request failed (${xhr.status})`));
    };
    xhr.send(formData);
  });
}

export async function confirmImport(
  token: string,
  contactId: string,
  previewId: string,
  contactIdentifier?: string,
): Promise<ImportUploadResponse> {
  return request<ImportUploadResponse>(
    `/api/contacts/${contactId}/imports/confirm`,
    {
      method: "POST",
      body: JSON.stringify({
        preview_id: previewId,
        run_analysis: true,
        contact_identifier: contactIdentifier,
      }),
    },
    token,
  );
}

export async function getImportStatus(
  token: string,
  contactId: string,
  importId: string,
): Promise<ImportStatusResponse> {
  return request<ImportStatusResponse>(`/api/contacts/${contactId}/imports/${importId}`, {}, token);
}

export async function retryImport(
  token: string,
  contactId: string,
  importId: string,
): Promise<ImportStatusResponse> {
  return request<ImportStatusResponse>(
    `/api/contacts/${contactId}/imports/${importId}/retry`,
    { method: "POST" },
    token,
  );
}

export function storageKeys() {
  return {
    auth: "textpulse-auth",
    demo: "textpulse-demo",
  };
}

export function readStoredAuth(): AuthResponse | null {
  if (!isBrowser()) {
    return null;
  }
  const raw = window.localStorage.getItem(storageKeys().auth);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as AuthResponse;
  } catch {
    return null;
  }
}

export function writeStoredAuth(value: AuthResponse | null) {
  if (!isBrowser()) {
    return;
  }
  if (!value) {
    window.localStorage.removeItem(storageKeys().auth);
    return;
  }
  window.localStorage.setItem(storageKeys().auth, JSON.stringify(value));
}
