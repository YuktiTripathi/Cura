import { useCallback, useState } from "react";
import { getDocument, uploadDocument, type UploadedDocument } from "../lib/api";

export type UploadChip = {
  localName: string;
  status: "uploading" | "uploaded" | "failed";
  document?: UploadedDocument;
  error?: string;
};

export type DocumentUploader = {
  chip: UploadChip | null;
  upload: (file: File) => Promise<void>;
  retry: () => void;
  clear: () => void;
};

const isPdf = (file: File) => file.type === "application/pdf" || /\.pdf$/i.test(file.name);

/**
 * Upload a PDF and follow its extraction until measurements are ready. Shared by the composer's
 * attach button and the page-wide drop zone so both show the same attachment.
 */
export function useDocumentUpload(conversationId: string | null, onUploaded?: () => void): DocumentUploader {
  const [chip, setChip] = useState<UploadChip | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);

  const pollExtraction = useCallback(
    async (documentId: string, name: string) => {
      for (let i = 0; i < 30; i += 1) {
        await new Promise((r) => setTimeout(r, 1000));
        try {
          const doc = await getDocument(documentId);
          if (doc.extraction_status === "failed") {
            setChip({ localName: name, status: "uploaded", document: doc });
            onUploaded?.();
            return;
          }
          if (doc.structured_facts_ready || doc.extraction_status === "completed") {
            setChip({ localName: name, status: "uploaded", document: doc });
            onUploaded?.();
            const idx = doc.pageindex_status;
            if (!idx || (idx !== "BUILDING" && idx !== "NOT_STARTED")) return;
          }
        } catch {
          return;
        }
      }
    },
    [onUploaded]
  );

  const upload = useCallback(
    async (file: File) => {
      if (!isPdf(file)) {
        setChip({ localName: file.name, status: "failed", error: "Only PDF reports can be added." });
        setPendingFile(null);
        return;
      }
      setChip({ localName: file.name, status: "uploading" });
      setPendingFile(file);
      try {
        const doc = await uploadDocument(file, conversationId);
        setChip({ localName: file.name, status: "uploaded", document: doc });
        setPendingFile(null);
        onUploaded?.();
        if (doc.extraction_status === "processing" || doc.extraction_status === "not_started") {
          void pollExtraction(doc.document_id, file.name);
        }
      } catch (err) {
        setChip({ localName: file.name, status: "failed", error: err instanceof Error ? err.message : undefined });
      }
    },
    [conversationId, onUploaded, pollExtraction]
  );

  return {
    chip,
    upload,
    retry: () => {
      if (pendingFile) void upload(pendingFile);
    },
    clear: () => {
      setChip(null);
      setPendingFile(null);
    },
  };
}
