# Chat orchestration

A chat turn runs four steps in `ChatService.chat`: execute, shape, finalize, and persist. That native sequence is the only orchestration path.

The system prompt sent to the answer model is the compact house prompt in `HOUSE_CORE`. Uploaded-document explanations use the separate document prompt in `prompt_modules.DOCUMENT_EXPLANATION`.

LangChain is not used.
