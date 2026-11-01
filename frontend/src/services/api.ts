import {
  Region,
  WorkloadConfig,
  OptimizationDecision,
  KPISummary,
  HealthStatus,
  TimeSeriesPoint,
  SettingsData,
} from '../types';

const API_BASE = '/api';

export const api = {
  async getHealth(): Promise<HealthStatus> {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error('Failed to fetch health status');
    return res.json();
  },

  async getRegions(): Promise<Region[]> {
    const res = await fetch(`${API_BASE}/regions`);
    if (!res.ok) throw new Error('Failed to fetch regions');
    return res.json();
  },

  async getTopology(): Promise<any> {
    const res = await fetch(`${API_BASE}/topology`);
    if (!res.ok) throw new Error('Failed to fetch topology');
    return res.json();
  },

  async getWorkloads(): Promise<WorkloadConfig[]> {
    const res = await fetch(`${API_BASE}/workloads`);
    if (!res.ok) throw new Error('Failed to fetch workloads');
    return res.json();
  },

  async getKPISummary(): Promise<KPISummary> {
    const res = await fetch(`${API_BASE}/metrics/summary`);
    if (!res.ok) throw new Error('Failed to fetch KPI summary');
    return res.json();
  },

  async getMetricsHistory(timeWindow: string = '1h'): Promise<TimeSeriesPoint[]> {
    const res = await fetch(`${API_BASE}/metrics/history?time_window=${timeWindow}`);
    if (!res.ok) throw new Error('Failed to fetch metrics history');
    return res.json();
  },

  async runOptimization(payload: {
    workload_id?: string;
    max_latency_ms?: number;
    min_carbon_pct?: number;
    dry_run?: boolean;
  }): Promise<OptimizationDecision> {
    const res = await fetch(`${API_BASE}/optimization/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Failed to run optimization');
    return res.json();
  },

  async getRecommendations(limit: number = 10): Promise<OptimizationDecision[]> {
    const res = await fetch(`${API_BASE}/optimization/recommendations?limit=${limit}`);
    if (!res.ok) throw new Error('Failed to fetch recommendations');
    return res.json();
  },

  async approveRecommendation(
    decisionId: string,
    operatorNotes?: string
  ): Promise<{ success: boolean; decision: OptimizationDecision; current_topology: Region[] }> {
    const res = await fetch(`${API_BASE}/optimization/recommendations/${decisionId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operator_notes: operatorNotes, operator_confirmed: true }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to approve recommendation');
    }
    return res.json();
  },

  async rejectRecommendation(
    decisionId: string,
    reason: string
  ): Promise<{ success: boolean; decision: OptimizationDecision }> {
    const res = await fetch(`${API_BASE}/optimization/recommendations/${decisionId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to reject recommendation');
    }
    return res.json();
  },

  async getMemoryHistory(params?: {
    limit?: number;
    workload_id?: string;
    region_id?: string;
    status?: string;
  }): Promise<OptimizationDecision[]> {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.workload_id) searchParams.set('workload_id', params.workload_id);
    if (params?.region_id) searchParams.set('region_id', params.region_id);
    if (params?.status) searchParams.set('status', params.status);

    const res = await fetch(`${API_BASE}/memory/history?${searchParams.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch decision history');
    return res.json();
  },

  async getSettings(): Promise<SettingsData> {
    const res = await fetch(`${API_BASE}/settings`);
    if (!res.ok) throw new Error('Failed to fetch settings');
    return res.json();
  },

  async updateSettings(payload: Partial<SettingsData>): Promise<{ success: boolean; settings: SettingsData }> {
    const res = await fetch(`${API_BASE}/settings`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to update settings');
    }
    return res.json();
  },

  async resetSimulation(): Promise<{ success: boolean; message: string; topology: Region[] }> {
    const res = await fetch(`${API_BASE}/simulation/reset`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to reset simulation');
    return res.json();
  },

  async getMekoPeaks(): Promise<import('../types').RegionalPeakSchedule[]> {
    const res = await fetch(`${API_BASE}/meko/peaks`);
    if (!res.ok) throw new Error('Failed to fetch Meko regional peak schedules');
    return res.json();
  },

  async getMekoContext(workloadId?: string): Promise<import('../types').MekoContextDossier> {
    const url = workloadId ? `${API_BASE}/meko/context?workload_id=${workloadId}` : `${API_BASE}/meko/context`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch Meko context dossier');
    return res.json();
  },
};

