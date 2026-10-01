import { assistantTextSegments, displayAssistantText } from "../../types/chat";
import { debugMode } from "./debug";

export function AssistantBody({ content }: { content: string }) {
  const text = displayAssistantText(content, debugMode());
  const lines = text.split("\n");
  return (
    <>
      {lines.map((line, index) => (
        <span key={index}>
          {index > 0 ? <br /> : null}
          {assistantTextSegments(line).map((part, partIndex) =>
            part.bold ? <strong key={partIndex}>{part.text}</strong> : <span key={partIndex}>{part.text}</span>
          )}
        </span>
      ))}
    </>
  );
}
