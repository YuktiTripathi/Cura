import { useState } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { createQueryClient } from "./lib/queryClient";
import { CuraPage } from "./pages/CuraPage";
import { CompanionPrototype } from "./prototype/CompanionPrototype";

function showPrototype(): boolean {
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("prototype") === "1";
}

export function App() {
  const [client] = useState(createQueryClient);
  return (
    <QueryClientProvider client={client}>
      {showPrototype() ? <CompanionPrototype /> : <CuraPage />}
    </QueryClientProvider>
  );
}
