import { test, expect } from "@playwright/test";

test("discovery, persistence, matching, filtering, and mobile layout", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  const cards = page.locator(".event-card");
  await expect(cards.first()).toBeVisible();
  const first = cards.first();
  const title = (await first.locator("h3").innerText()).trim();
  await first
    .getByRole("button", { name: `Save ${title}`, exact: true })
    .click();
  await page.getByRole("button", { name: /^Saved/ }).click();
  await expect(cards).toHaveCount(1);
  await page.reload();
  await page.getByRole("button", { name: /^Saved/ }).click();
  await expect(cards).toHaveCount(1);
  await page.getByRole("button", { name: "Discover", exact: true }).click();
  await cards.first().locator("h3 button").click();
  await expect(
    page.getByRole("heading", { name: "Compare availability" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close event details" }).click();
  await page.getByRole("button", { name: "Matching lab", exact: true }).click();
  await page.getByRole("button", { name: "Run matching", exact: true }).click();
  await expect(
    page.getByText("Matched confidently", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close matching lab" }).click();
  await page
    .getByRole("textbox", { name: "Search events" })
    .fill("Velvt Echoes");
  await expect(
    page.getByRole("heading", { name: "Results for “Velvt Echoes”" }),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "City", exact: true })
    .selectOption("Seattle");
  await expect
    .poll(async () => await page.locator(".event-location").allTextContents())
    .toEqual(expect.arrayContaining([expect.stringContaining("Seattle")]));
  await expect
    .poll(async () =>
      (await page.locator(".event-location").allTextContents()).every((c) =>
        c.includes("Seattle"),
      ),
    )
    .toBe(true);
  await page.getByRole("button", { name: "Filters", exact: true }).click();
  await page.getByLabel("Maximum price ($)", { exact: true }).fill("0");
  await expect(
    page.getByText("No events found.", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Reset filters" }).click();
  await page.getByRole("button", { name: "Clear search" }).click();
  await page
    .getByRole("combobox", { name: "City", exact: true })
    .selectOption("");
  await expect(cards.first()).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
