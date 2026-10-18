import { beforeEach, expect, it, vi } from "vitest";

import {
  ApiError,
  discoverSchema,
  getSession,
  getTemplate,
  listClients,
  pageImageUrl,
  templatePageUrl,
} from "./api";

beforeEach(() => {
  vi.restoreAllMocks();
});

it("parses the client list", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            clients: [
              { name: "uni-hamburg", institution_name: "Universität Hamburg", configured: true },
            ],
          }),
          { status: 200 }
        )
    )
  );

  expect((await listClients())[0].institution_name).toBe("Universität Hamburg");
});

it("turns an error status into an ApiError", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({ status: "error", error: "This PDF has no fillable form fields" }),
          { status: 200 }
        )
    )
  );

  await expect(discoverSchema(new File(["x"], "f.pdf"))).rejects.toBeInstanceOf(ApiError);
});

it("turns a 500 into a plain ApiError", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response("boom", { status: 500 })));

  await expect(listClients()).rejects.toBeInstanceOf(ApiError);
});

it("parses the session manifest", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            session_id: "s1",
            client_name: "uni-ulm",
            field_count: 3,
            documents: [{ name: "hotel.pdf", page_count: 2 }],
          }),
          { status: 200 }
        )
    )
  );

  expect((await getSession("s1")).documents[0]).toEqual({
    name: "hotel.pdf",
    page_count: 2,
  });
});

it("builds the page image URL", () => {
  expect(pageImageUrl("s1", 0, 1)).toBe(
    "http://localhost:8000/api/extract/session/s1/pages/0/1.jpg"
  );
});

it("parses the template preview manifest", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            pages: [{ page: 0, width: 1654, height: 2339 }],
            fields: [
              { field_name: "Reiseziel", page: 0, x: 10, y: 20, width: 30, height: 8 },
            ],
          }),
          { status: 200 }
        )
    )
  );

  expect((await getTemplate("s1")).fields[0].field_name).toBe("Reiseziel");
});

it("builds the template page URL", () => {
  expect(templatePageUrl("s1", 2)).toBe(
    "http://localhost:8000/api/extract/session/s1/template/pages/2.jpg"
  );
});
