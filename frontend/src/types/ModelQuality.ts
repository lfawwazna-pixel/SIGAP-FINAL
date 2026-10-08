/* Generated from contracts/model_quality.py. Do not edit manually. */

export type Available = boolean;
export type ModelLabel = string;
export type ModelSha256 = string | null;
export type Precision = number;
export type Recall = number;
export type Map50 = number;
export type Map5095 = number;
export type Limitations = string[];
export type Message = string;

export interface ModelQuality {
  available: Available;
  model_label: ModelLabel;
  model_sha256: ModelSha256;
  reports: Reports;
  limitations: Limitations;
  message: Message;
}
export interface Reports {
  [k: string]: EvaluationSplit;
}
export interface EvaluationSplit {
  per_class: PerClass;
}
export interface PerClass {
  [k: string]: ClassMetrics;
}
export interface ClassMetrics {
  precision: Precision;
  recall: Recall;
  map50: Map50;
  map5095: Map5095;
}
