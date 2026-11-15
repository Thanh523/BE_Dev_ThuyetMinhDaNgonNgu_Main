import "@testing-library/jest-dom/vitest";

globalThis.fetch = async () => {
  throw new Error("Unexpected fetch in component test");
};
