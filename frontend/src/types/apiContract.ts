/**
 * Compile-time drift checks between the hand-written UI types and the backend's OpenAPI schema
 * (src/types/api.generated.ts, produced by `npm run gen:api`).
 *
 * Each line asserts that every field the UI type declares still exists on the backend model.
 * If the backend renames or removes a field, `tsc` (and therefore `npm run build`) fails here
 * and names the missing key. Nothing in this file is emitted at runtime.
 */
import type { components } from "./api.generated";
import type {
  ChatMeta,
  ChatResponse,
  ContextRef,
  EvidenceItem,
  ExistingResult,
  FollowUp,
  HealthTheme,
  PackageAction,
  PackageComparison,
  PresentedFinding,
  ProvenanceSource,
  Recommendation,
  StructuredResponse,
  TestingOption,
  UserProvenance,
} from "./chat";
import type { MeCapabilities, MeResponse, StarterQuestion, StarterQuestionSet } from "./me";
import type { ConversationDetail, ConversationSummary, UploadedDocument } from "../lib/api";

type Schemas = components["schemas"];

/** Resolves to `true` when every key of Local exists on Remote; otherwise to the missing keys. */
type KeysExistOn<Local, Remote> = [Exclude<keyof Local, keyof Remote>] extends [never]
  ? true
  : { missingOnBackend: Exclude<keyof Local, keyof Remote> };

type Expect<T extends true> = T;

export type ApiContractChecks = [
  Expect<KeysExistOn<ChatResponse, Schemas["ChatResponse"]>>,
  Expect<KeysExistOn<ChatMeta, Schemas["ChatMeta"]>>,
  Expect<KeysExistOn<EvidenceItem, Schemas["EvidenceItem"]>>,
  Expect<KeysExistOn<FollowUp, Schemas["FollowUpSuggestion"]>>,
  Expect<KeysExistOn<Recommendation, Schemas["ApprovedRecommendation"]>>,
  Expect<KeysExistOn<ContextRef, Schemas["ContextRef"]>>,
  Expect<KeysExistOn<UserProvenance, Schemas["UserProvenance"]>>,
  Expect<KeysExistOn<ProvenanceSource, Schemas["ProvenanceSource"]>>,
  Expect<KeysExistOn<StructuredResponse, Schemas["StructuredResponse"]>>,
  Expect<KeysExistOn<PresentedFinding, Schemas["PresentedFinding"]>>,
  Expect<KeysExistOn<HealthTheme, Schemas["HealthTheme"]>>,
  Expect<KeysExistOn<TestingOption, Schemas["TestingOption"]>>,
  Expect<KeysExistOn<PackageAction, Schemas["PackageAction"]>>,
  Expect<KeysExistOn<PackageComparison, Schemas["PackageComparison"]>>,
  Expect<KeysExistOn<ExistingResult, Schemas["ExistingResult"]>>,
  Expect<KeysExistOn<MeResponse, Schemas["MeResponse"]>>,
  Expect<KeysExistOn<MeCapabilities, Schemas["MeCapabilities"]>>,
  Expect<KeysExistOn<StarterQuestion, Schemas["StarterQuestion"]>>,
  Expect<KeysExistOn<StarterQuestionSet, Schemas["StarterQuestionSet"]>>,
  Expect<KeysExistOn<UploadedDocument, Schemas["DocumentOut"]>>,
  Expect<KeysExistOn<ConversationSummary, Schemas["ConversationSummary"]>>,
  Expect<KeysExistOn<ConversationDetail, Schemas["ConversationDetail"]>>,
];
