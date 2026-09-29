export type MeCapabilities = {
  has_blood_report: boolean;
  has_bio_ai_report: boolean;
  has_questionnaire: boolean;
  has_nutrition: boolean;
  has_health_scenario: boolean;
  has_health_goals?: boolean;
};

export type StarterQuestion = {
  text: string;
  knowledge_scope: string;
  category: string;
};

export type StarterQuestionSet = {
  personal: StarterQuestion[];
  general: StarterQuestion[];
  personal_unavailable: boolean;
};

export type MeResponse = {
  user_id: string | number | null;
  first_name: string | null;
  last_name: string | null;
  display_name: string | null;
  greeting: string;
  profile_available: boolean;
  capabilities: MeCapabilities;
  starters?: StarterQuestionSet;
};
