export type Client = {
  name: string;
  institution_name: string;
  configured: boolean;
};

export type ProposedField = {
  name: string;
  field_type: string;
  description: string | null;
  required: boolean;
};

export type Proposal = {
  proposal_id: string;
  institution_name: string;
  form_title: string;
  form_language: string;
  field_count: number;
  fields: ProposedField[];
};

export type BoundingBox = {
  page: number;
  x: number;
  y: number;
  width: number;
  height: number;
};

export type ExtractedField = {
  field_name: string;
  semantic_name?: string | null;
  value: string;
  source_document: string;
  bounding_box: BoundingBox | null;
  confidence: number;
  reasoning: string | null;
};

export type SessionDocument = {
  name: string;
  page_count: number;
};

export type SessionInfo = {
  session_id: string;
  client_name: string;
  field_count: number;
  documents: SessionDocument[];
};

export type TemplatePage = {
  page: number;
  width: number;
  height: number;
};

/** A form line that will receive a value, in the rendered page's pixels. */
export type TemplateField = BoundingBox & {
  field_name: string;
};

export type TemplateInfo = {
  pages: TemplatePage[];
  fields: TemplateField[];
};

export type ExtractionResult = {
  session_id: string;
  extracted_fields: ExtractedField[];
};

/** Any failure the traveller could be shown, carrying a plain-language message. */
export class ApiError extends Error {}

const FALLBACK = "Something went wrong. Please try again.";

export function apiUrl(path: string): string {
  const base =
    (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";
  return `${base.replace(/\/$/, "")}${path}`;
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (typeof body?.error === "string") return body.error;
  } catch {
    // Not JSON; fall through to the generic message.
  }
  return FALLBACK;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), init);
  } catch {
    throw new ApiError("Could not reach the server. Please try again.");
  }

  if (!response.ok) {
    throw new ApiError(await errorMessage(response));
  }

  const body = (await response.json()) as { status?: string; error?: string };

  // Discovery reports a failed upload as a 200 with an error status.
  if (body && body.status === "error") {
    throw new ApiError(body.error || FALLBACK);
  }

  return body as T;
}

export async function listClients(): Promise<Client[]> {
  const body = await request<{ clients: Client[] }>("/api/forms/clients");
  return body.clients;
}

export async function discoverSchema(file: File): Promise<Proposal> {
  const data = new FormData();
  data.append("form_template", file);
  return request<Proposal>("/api/forms/discover-schema", { method: "POST", body: data });
}

export async function confirmSchema(
  proposalId: string,
  institutionName: string
): Promise<{ client_name: string; institution_name: string }> {
  return request("/api/forms/confirm-schema", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      proposal_id: proposalId,
      institution_name: institutionName,
    }),
  });
}

export async function extract(
  clientName: string,
  files: File[]
): Promise<ExtractionResult> {
  const data = new FormData();
  data.append("client_name", clientName);
  for (const file of files) {
    data.append("receipts", file);
  }
  return request<ExtractionResult>("/api/extract/process", {
    method: "POST",
    body: data,
  });
}

export async function verify(input: {
  sessionId: string;
  verifiedFields: Record<string, string>;
  keptFields: string[];
}): Promise<{ download_url: string; unmatched_fields?: string[] }> {
  // The wire body is snake_case; the camelCase names are only for callers.
  return request("/api/extract/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: input.sessionId,
      verified_fields: input.verifiedFields,
      kept_fields: input.keptFields,
    }),
  });
}

export async function getSession(sessionId: string): Promise<SessionInfo> {
  return request<SessionInfo>(`/api/extract/session/${sessionId}`);
}

export function pageImageUrl(sessionId: string, docIndex: number, page: number): string {
  return apiUrl(`/api/extract/session/${sessionId}/pages/${docIndex}/${page}.jpg`);
}

export async function getTemplate(sessionId: string): Promise<TemplateInfo> {
  return request<TemplateInfo>(`/api/extract/session/${sessionId}/template`);
}

export function templatePageUrl(sessionId: string, page: number): string {
  return apiUrl(`/api/extract/session/${sessionId}/template/pages/${page}.jpg`);
}
