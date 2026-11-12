import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { kg, km, minutes, shortId, statusTone, titleCase } from "../lib/format";
import { EmptyState, ErrorState, Progress, StatusBadge } from "./ui";

describe("format helpers", () => {
  it("formats logistics units", () => {
    expect(km(1500)).toBe("1.5 km");
    expect(minutes(3600)).toBe("60 min");
    expect(kg("1250")).toContain("1,250 kg");
    expect(shortId("abcdef1234567890")).toBe("abcdef12…");
    expect(shortId(null)).toBe("—");
    expect(titleCase("PENDING_ALLOCATION")).toBe("Pending Allocation");
  });

  it("gives known statuses a distinct tone", () => {
    expect(statusTone("DELIVERED")).not.toBe(statusTone("FAILED"));
    expect(statusTone("SOMETHING_NEW")).toContain("slate");
  });
});

describe("ui error and state primitives", () => {
  it("renders the request id so a failure can be correlated", () => {
    render(
      <ErrorState
        error={new ApiError(503, "service_unavailable", "Database is unavailable", "req-42")}
        onRetry={() => undefined}
      />,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Service unavailable")).toBeInTheDocument();
    expect(screen.getByText(/req-42/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("invokes the retry handler", async () => {
    const onRetry = vi.fn();
    render(<ErrorState error={new Error("nope")} onRetry={onRetry} />);
    screen.getByRole("button", { name: /retry/i }).click();
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("renders an empty state and a status badge", () => {
    render(<EmptyState title="No orders match" hint="Adjust the filter" />);
    expect(screen.getByText("No orders match")).toBeInTheDocument();
    expect(screen.getByText("Adjust the filter")).toBeInTheDocument();

    render(<StatusBadge status="PENDING_ALLOCATION" />);
    expect(screen.getByText("Pending Allocation")).toBeInTheDocument();
  });

  it("clamps progress to 0-100", () => {
    const { rerender } = render(<Progress value={-10} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");
    rerender(<Progress value={250} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
  });
});
