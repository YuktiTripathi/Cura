export type GreetingId = "first_with_reports" | "returning" | "new_report" | "long_absence" | "no_reports" | "continue_conversation";

export type GreetingCopy = {
  id: GreetingId;
  heading: (name: string | null) => string;
  primary: string;
  supporting: (topic?: string | null) => string;
};

export const GREETINGS: Record<GreetingId, GreetingCopy> = {
  first_with_reports: {
    id: "first_with_reports",
    heading: (name) => (name ? `Hi ${name} 👋` : "Hi there 👋"),
    primary: "Let's get to know your health, together.",
    supporting: () =>
      "Your health is more than just numbers on a report. I'm here to help you understand what they mean, how they connect, and what you can do to feel your best.",
  },
  returning: {
    id: "returning",
    heading: (name) => (name ? `Welcome back, ${name} 👋` : "Welcome back 👋"),
    primary: "The more you understand your health, the better it gets.",
    supporting: () =>
      "Whether you're curious about your results, looking to build healthier habits, or simply have a question, I'm here to help.",
  },
  new_report: {
    id: "new_report",
    heading: (name) => (name ? `Hi ${name} 👋` : "Hi there 👋"),
    primary: "Your new health results are here!",
    supporting: () =>
      "Let's understand what your body is telling you, what these results mean for your everyday life, and what you can do next.",
  },
  long_absence: {
    id: "long_absence",
    heading: (name) => (name ? `It's been a while, ${name} 👋` : "It's been a while 👋"),
    primary: "How have you been?",
    supporting: () =>
      "Today is a good day to reconnect with your health. Let's see where you are and take it one step at a time.",
  },
  no_reports: {
    id: "no_reports",
    heading: (name) => (name ? `Hi ${name} 👋` : "Hi there 👋"),
    primary: "Better health begins with curiosity.",
    supporting: () =>
      "From understanding your body to building healthier everyday habits, there's so much we can explore together. Feel free to ask me anything about your health.",
  },
  continue_conversation: {
    id: "continue_conversation",
    heading: (name) => (name ? `Good to see you again, ${name} 👋` : "Good to see you again 👋"),
    primary: "Let's pick up where we left off.",
    supporting: (topic) =>
      `Last time, we talked about ${topic}. We can explore it a little further or talk about something new today.`,
  },
};

export const CARD_COPY = {
  understand: {
    title: "Understand my health",
    description: "Discover what your health results mean for you.",
    descriptionWithoutReports: "Learn how your body works and what your health tests can tell you.",
  },
  eat: {
    title: "Eat better for my body",
    description: "Explore food choices that support your health.",
  },
  talk: {
    title: "Let's talk about health",
    description: "Ask me anything you're curious or concerned about.",
  },
} as const;

export const QUESTIONS_WITH_REPORTS = [
  "Which of my health results should I focus on first?",
  "What do my results tell me about my health?",
  "How can I improve my health through everyday habits?",
];

export const QUESTIONS_WITHOUT_REPORTS = [
  "How can I build healthier everyday habits?",
  "What can a blood test tell me about my health?",
  "How does sleep affect my health?",
  "How can I make better food choices?",
];
