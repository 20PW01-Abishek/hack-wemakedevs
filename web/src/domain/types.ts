export interface GraphNode {
  id: string;
  label: string;
}

export interface GraphEdge {
  from: string;
  type: string;
  to: string;
}

export interface PathGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface ToolStep {
  name: string;
  args: Record<string, unknown>;
}

export interface Message {
  role: "user" | "assistant";
  text: string;
  steps?: ToolStep[];
  graph?: PathGraph | null;
}

export interface ChatSession {
  id: string;
  title: string;
  created: string;
  shared: boolean;
}

export interface Account {
  user: string;
  admin: boolean;
}

export interface Credentials {
  username: string;
  password: string;
}

export interface NewUser extends Credentials {
  admin: boolean;
}

export interface StaleDoc {
  doc: string;
  url: string | null;
  doc_updated: string;
  concept: string;
  current_value: string | null;
  decision: string;
  decided: string;
  decision_source: string | null;
  people_reading_it: string[];
}

export interface LearnedDocument {
  summary: string;
  decisions: { summary: string; approved_by?: string | null }[];
}

export interface ChatReply {
  session: string;
  answer: string;
  steps: ToolStep[];
  graph: PathGraph | null;
}

export interface ContextDocument {
  id: string;
  name: string;
  url: string | null;
  updated: string;
  summary: string | null;
  chunks: number;
}

export interface UserAccount {
  username: string;
  admin: boolean;
}

export interface Notice {
  text: string;
  error: boolean;
}
