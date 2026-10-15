import { beforeEach, expect, it, vi } from "vitest";

import { ApiError, discoverSchema, listClients } from "./api";

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
