import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "./api";

const jsonResponse = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

afterEach(() => {
  vi.restoreAllMocks();
});

describe("api error handling", () => {
  it("maps the backend error envelope onto ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() =>
        Promise.resolve(
          jsonResponse(409, {
            error: {
              code: "conflict",
              message: "Insufficient inventory: A requested 5, available 1",
              request_id: "abc123",
              details: null,
            },
          }),
        ),
      ),
    );

    await expect(api.optimize()).rejects.toMatchObject({
      status: 409,
      code: "conflict",
      requestId: "abc123",
    });
    await expect(api.optimize()).rejects.toThrow(/Insufficient inventory/);
  });

  it("reports network failure as a retryable ApiError rather than crashing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed")));

    const error = await api.optimize().catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.isNetwork).toBe(true);
    expect(error.isUnavailable).toBe(true);
  });

  it("does not retry mutations, but retries safe reads once transient", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(503, { error: { code: "service_unavailable", message: "down" } }))
      .mockResolvedValueOnce(jsonResponse(200, { status: "ok", database: "connected", redis: "connected" }))
      .mockResolvedValueOnce(jsonResponse(500, { error: { code: "error", message: "boom" } }));
    vi.stubGlobal("fetch", fetchMock);

    // GET /health retries the 503 and succeeds on the second attempt.
    await expect(api.health()).resolves.toMatchObject({ status: "ok" });
    expect(fetchMock).toHaveBeenCalledTimes(2);

    fetchMock.mockClear();
    // A POST must never be retried automatically.
    await expect(api.optimize()).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("falls back to a generic message for non-JSON error bodies", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("<html>gateway</html>", { status: 502 })),
    );

    const error = await api.health().catch((e) => e);
    expect(error.status).toBe(502);
    expect(error.message).toContain("502");
  });
});
