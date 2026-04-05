import { ContactWorkspace } from "@/components/contact-workspace";

export default async function ContactPage({
  params,
}: {
  params: Promise<{ contactId: string }>;
}) {
  const { contactId } = await params;
  return <ContactWorkspace contactId={contactId} />;
}
