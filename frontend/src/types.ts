// ViralCut shared types

export interface Segment {
  segment_id: string;
  function: string;
  start_time: number;
  end_time: number;
  hook_type?: string;
  core_text: string;
  evidence: { type: string; ref: string; text: string }[];
  reason: string;
  confidence: number;
}

export interface ScriptStructure {
  segments: Segment[];
  hook_type: string;
  cta_type: string | null;
  structure_pattern: string;
  uncertainty: string;
}

export interface SegmentRhythm {
  segment_id: string;
  time_range: [number, number];
  pace: string;
  shots_per_second: number;
  avg_shot_duration: number;
  beat_count: number;
  cut_beat_alignment: number;
  rhythm_driver?: string;
  role: string;
  reason: string;
}

export interface RhythmStructure {
  overall_rhythm: { pace: string; bpm: number; beat_sync_score: number; avg_shot_duration: number };
  segment_rhythm: SegmentRhythm[];
  rhythm_pattern: string;
  climax_analysis: { confirmed: boolean; confirmed_range: [number, number]; reason: string };
}

export interface EnergyPoint {
  segment_id: string;
  time_range: [number, number];
  energy_level: string;
  role: string;
  drivers: string[];
  evidence_refs?: string[];
  confidence?: number;
}

export interface EnergyCurve {
  energy_curve: EnergyPoint[];
  energy_pattern: string;
  peak_position?: number;
}

export interface Slot {
  slot_id: string;
  slot_type: string;
  source_time_range?: [number, number];
  duration_seconds: number;
  duration_ratio?: number;
  purpose: string;
  template?: string;
  required_elements?: string[];
  replaceable_elements?: string[];
  input_requirements?: {
    needed_assets: string[];
    min_clip_count: number;
    visual_constraints: string[];
  };
  priority?: string;
}

export interface TransferBlueprint {
  source_video_type: string;
  structure_template: Slot[];
  editing_rules: { rule_name?: string; rule?: string; description: string; priority?: string }[];
  adaptation_guidance: Record<string, string>;
}

export interface VideoStructure {
  video_id: string;
  duration: number;
  script_structure: ScriptStructure;
  rhythm_structure: RhythmStructure;
  packaging_structure: { packaging_structure: Record<string, unknown>; segment_packaging?: unknown[] };
  value_strategy: { value_strategy: Record<string, unknown> };
  energy_curve: EnergyCurve;
  transfer_blueprint: { transfer_blueprint: TransferBlueprint };
  evaluation?: { status: string; score: number; checks: unknown[] };
  analysis_metadata?: Record<string, unknown>;
}

export interface AnalysisResult {
  video_id: string;
  video_url: string;
  video_structure: VideoStructure;
  evidence_package: Record<string, unknown> | null;
}

// Stage 3 migration types
export interface MigratedSlot {
  slot_id: string;
  slot_type: string;
  duration_seconds: number;
  status: 'filled' | 'gap' | 'restructured' | 'aigc_needed';
  migrated_content: { text?: string; visual?: string };
  matched_assets: string[];
  gap: { missing: string; affected_requirement: string } | null;
  fill_strategy: { type: string; description: string; alternative?: string } | null;
  reason: string;
}

export interface MigrationResult {
  new_video_type: string;
  migration_summary: string;
  overall_feasibility: number;
  migrated_slots: MigratedSlot[];
  gap_summary: { total_slots: number; filled: number; gaps: number; gap_slots: string[] };
  applied_rules: string[];
  new_script: string;
}
