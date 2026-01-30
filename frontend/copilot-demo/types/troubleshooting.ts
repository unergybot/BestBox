// frontend/copilot-demo/types/troubleshooting.ts

export interface TroubleshootingImage {
  image_id: string;
  image_url: string;
  description: string;
  defect_type: string;
  file_path?: string;
  cell_location?: string;
  vl_description?: string | null;
  text_in_image?: string | null;
  equipment_part?: string;
  visual_annotations?: string;
}

export interface TroubleshootingIssue {
  result_type: "specific_solution";
  relevance_score: number;
  case_id: string;
  part_number: string;
  issue_number: number;
  problem: string;
  solution: string;
  trial_version: string;
  result_t1?: string | null;
  result_t2?: string | null;
  success_status?: string | null;
  defect_types?: string[];
  has_images: boolean;
  image_count: number;
  images: TroubleshootingImage[];
  category?: string;
}

export interface TroubleshootingCase {
  result_type: "full_case";
  relevance_score: number;
  case_id: string;
  part_number: string;
  material: string;
  total_issues: number;
  summary: string;
  source_file?: string;
}

export type TroubleshootingResult = TroubleshootingIssue | TroubleshootingCase;

export interface TroubleshootingSearchResults {
  query: string;
  search_mode: string;
  total_found: number;
  results: TroubleshootingResult[];
}
