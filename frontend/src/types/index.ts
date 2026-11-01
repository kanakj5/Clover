export type RegionId = 'mumbai' | 'frankfurt' | 'virginia';

export interface RegionInfo {
  id: RegionId;
  name: string;
  country: string;
  flag: string;
  code: string;
  cloudZone: string;
  basePowerKw: number; // Node baseline server power (kW)
  gridFuelMix: string;
  baseElectricityPrice: number; // $/MWh
}

export interface RegionHourlyData {
  hour: number;
  carbonIntensity: number; // gCO2 / kWh
  electricityPrice: number; // $/MWh
  solarFactor: number;
  windFactor: number;
}

export interface RegionState {
  id: RegionId;
  name: string;
  flag: string;
  code: string;
  cloudZone: string;
  carbonIntensity: number; // gCO2 / kWh
  electricityPrice: number; // $/MWh
  avgNetworkLatencyMs: number; // ms to global clients
  activeLeaders: number; // number of tablet leaders hosted
  totalReplicas: number; // total replicas in this region
  workloadEnergyKwh: number; // calculated hourly energy
  gridFuelMix: string;
  isCleanest: boolean;
}

export interface TabletInfo {
  id: string;
  tableName: string;
  keyspace: string;
  leaderRegion: RegionId;
  replicas: RegionId[];
  isLatencyCritical: boolean; // e.g., checkout/payments vs analytics/catalog
  readsPerSec: number;
  writesPerSec: number;
}

export interface MekoDecision {
  status: 'ACCEPTED' | 'REJECTED' | 'NO_CHANGE';
  sourceRegion: RegionId | null;
  targetRegion: RegionId | null;
  leadersToMove: number;
  candidateTabletIds: string[];
  currentHourlyCarbonG: number;
  projectedHourlyCarbonG: number;
  carbonSavedG: number;
  carbonSavedPercent: number;
  currentP99LatencyMs: number;
  projectedP99LatencyMs: number;
  latencyDeltaMs: number;
  toleranceLimitMs: number;
  explanation: string;
  memoryFactorsTriggered?: string[];
  assumptions: string[];
  calculatedAt: string;
}

export interface MemoryRecord {
  id: string;
  timestamp: string;
  simulatedHour: number;
  action: string;
  sourceRegion: RegionId;
  targetRegion: RegionId;
  leadersMoved: number;
  carbonSavedG: number;
  latencyDeltaMs: number;
  observedP99Ms: number;
  outcome: 'SUCCESS' | 'LATENCY_SPIKE' | 'REJECTED_BY_BUDGET' | 'REVERTED';
  lessonText: string;
  tags: string[];
}

export interface ClusterMetrics {
  hourlyCarbonGrams: number;
  carbonPer1kTxG: number;
  totalCarbonSavedKg: number;
  carbonSavedPercentage: number;
  currentP99LatencyMs: number;
  baselineP99LatencyMs: number;
  totalTransactionsPerHour: number;
  totalLeaders: number;
  optimizationStatus: 'OPTIMIZED' | 'OPPORTUNITY_DETECTED' | 'LATENCY_CONSTRAINED' | 'BALANCING';
}

export interface SimulationState {
  currentHour: number; // 0 to 23
  isPlaying: boolean;
  playbackSpeed: number; // ms per tick
  latencyToleranceMs: number; // 0 to 100 ms
  tablets: TabletInfo[];
  totalSavedCarbonAccumulatedG: number;
  activeOptimization: MekoDecision | null;
  lastAppliedHour: number | null;
}

// ============================================================================
// REST API & Extended Types (Connecting FastAPI Backend & Legacy Services)
// ============================================================================

export interface Region {
  id: RegionId | string;
  name: string;
  country?: string;
  flag?: string;
  code?: string;
  cloud_zone?: string;
  carbon_intensity_g_per_kwh: number;
  write_latency_ms: number;
  base_write_latency_ms?: number;
  is_healthy: boolean;
  electricity_price_usd_per_mwh?: number;
  electricity_price_usd_per_kwh?: number;
  current_leaders?: number;
  is_active_candidate?: boolean;
  is_leader?: boolean;
  energy_mix?: string;
  replica_count?: number;
}

export interface WorkloadConfig {
  id: string;
  name: string;
  description: string;
  priority: string;
  max_latency_budget_ms: number;
  max_p99_latency_ms?: number;
  energy_per_tx_kwh: number;
  tx_per_second: number;
  tps?: number;
  is_active: boolean;
}

export interface OptimizationDecision {
  id: string;
  timestamp: string;
  workload_id: string;
  workload_name?: string;
  current_region: string;
  current_region_id?: string;
  current_region_name?: string;
  current_carbon_intensity?: number;
  current_p99_latency_ms?: number;
  proposed_region: string;
  target_region_id?: string;
  target_region_name?: string;
  target_carbon_intensity?: number;
  target_p99_latency_ms?: number;
  latency_budget_ms?: number;
  status: string;
  decision_state?: string;
  carbon_before_g: number;
  carbon_after_g: number;
  carbon_reduction_pct: number;
  carbon_reduction_g_per_hr?: number;
  p99_latency_before_ms: number;
  p99_latency_after_ms: number;
  latency_impact_ms: number;
  latency_delta_ms?: number;
  electricity_price_usd_per_mwh?: number;
  reason: string;
  explanation?: string;
  operator_approved?: boolean;
  operator_notes?: string;
  created_at?: string;
  execution_time_ms?: number;
  meko_context?: any;
  ai_reasoning_steps?: string[];
  peak_hour_analysis?: string;
  rollback_plan?: string;
  is_dry_run?: boolean;
  ai_model?: string;
  ai_confidence_score?: number;
  historical_warning?: string;
}

export interface KPISummary {
  total_decisions: number;
  active_leaders_count: number;
  avg_carbon_reduction_pct: number;
  carbon_reduction_pct?: number;
  total_carbon_saved_g: number;
  avg_p99_latency_ms: number;
  current_p99_latency_ms?: number;
  current_cleanest_region: string;
  simulation_mode: boolean;
  is_simulated?: boolean;
  active_workload_name?: string;
  eligible_regions_count?: number;
  total_recommendations_count?: number;
  approved_changes_count?: number;
  rejected_changes_count?: number;
}

export interface HealthStatus {
  status: string;
  mode: string;
  operating_mode?: string;
  database_connected: boolean;
  meko_connected: boolean;
  is_live_db_connected?: boolean;
  db_status_details?: string;
  carbon_data_label?: string;
  yugabyte_host?: string;
  uptime_seconds?: number;
  timestamp: string;
}

export interface TimeSeriesPoint {
  timestamp: string;
  hour: number;
  mumbai_carbon: number;
  frankfurt_carbon: number;
  virginia_carbon: number;
  mumbai_latency: number;
  frankfurt_latency: number;
  virginia_latency: number;
}

export interface SettingsData {
  optimization_interval_sec: number;
  default_latency_tolerance_ms: number;
  min_carbon_reduction_pct: number;
  cooldown_period_sec: number;
  cooldown_seconds?: number;
  meko_enabled: boolean;
  dry_run_mode: boolean;
  dry_run_enabled?: boolean;
  cost_aware_enabled?: boolean;
  yugabyte_read_only: boolean;
  operating_mode?: string;
  carbon_provider?: string;
  max_latency_increase_ms?: number;
  yugabytedb_host?: string;
  yugabytedb_port?: number;
  yugabytedb_database?: string;
}

export interface RegionalPeakSchedule {
  region_id: string;
  region_name: string;
  name?: string;
  is_peak_now?: boolean;
  traffic_surge_factor?: number;
  local_time_display?: string;
  timezone_label?: string;
  carbon_surge_window?: string;
  peak_traffic_window: string;
  solar_peak_window: string;
  wind_peak_window: string;
  current_traffic_multiplier: number;
  current_carbon_intensity: number;
}

export interface MekoContextDossier {
  timestamp: string;
  target_workload: string;
  peak_insights: string[];
  memory_warnings: string[];
  recommended_clean_windows: string[];
  gemini_context_prompt: string;
}

