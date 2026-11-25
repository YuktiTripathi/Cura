const storage = window.localStorage;
if (!storage || typeof storage.getItem !== "function") {
  const memory = new Map<string, string>();
  const replacement: Storage = {
    get length() {
      return memory.size;
    },
    clear: () => memory.clear(),
    getItem: (key) => (memory.has(key) ? memory.get(key)! : null),
    key: (index) => [...memory.keys()][index] ?? null,
    removeItem: (key) => {
      memory.delete(key);
    },
    setItem: (key, value) => {
      memory.set(key, String(value));
    },
  };
  Object.defineProperty(window, "localStorage", { configurable: true, value: replacement });
}
