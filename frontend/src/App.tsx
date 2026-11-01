import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  SimulationState,
  MemoryRecord,
  MekoDecision,
} from './types';
import {
  loadSimulationState,
  saveSimulationState,
  loadMemoryRecords,
  saveMemoryRecords,
  addMemoryRecord,
  clearMemoryRecords,
  resetToSeedMemory,
} from './utils/storage';
import {
  calculateClusterMetrics,
  getRegionalStates,
  evaluateMekoOptimization,
  generate24HourTimelineData,
} from './utils/engine';
import { INITIAL_TABLETS } from './utils/carbonData';
import { TopNav } from './components/TopNav';
import { KpiMetrics } from './components/KpiMetrics';
import { RegionalMonitor } from './components/RegionalMonitor';
import { NetworkTopologyMap } from './components/NetworkTopologyMap';
import { MekoDecisionPanel } from './components/MekoDecisionPanel';
import { TradeoffChart } from './components/TradeoffChart';
import { MekoMemory } from './components/MekoMemory';
import { SimulationControls } from './components/SimulationControls';
import { YugabyteClusterView } from './components/YugabyteClusterView';
import { JudgeDemoModal } from './components/JudgeDemoModal';
import { MethodologyModal } from './components/MethodologyModal';
import { Sparkles, Bot, ShieldCheck, Zap, Activity, CheckCircle2, AlertTriangle } from 'lucide-react';

export const App: React.FC = () => {
  // Initialize persistent states from localStorage
  const [simState, setSimState] = useState<SimulationState>(() => loadSimulationState());
  const [memories, setMemories] = useState<MemoryRecord[]>(() => loadMemoryRecords());

  // Autonomous decision-making state: default ON (no manual approval required)
  const [autonomousMode, setAutonomousMode] = useState<boolean>(true);
  const [lastAutoAppliedKey, setLastAutoAppliedKey] = useState<string>('');
  const [autoExecutionToast, setAutoExecutionToast] = useState<string | null>(null);

  // UI state
  const [activeSection, setActiveSection] = useState<string>('overview');
  const [isJudgeDemoOpen, setIsJudgeDemoOpen] = useState<boolean>(false);
  const [isMethodologyOpen, setIsMethodologyOpen] = useState<boolean>(false);
  const [isApplied, setIsApplied] = useState<boolean>(false);

  // Sync state to local storage
  useEffect(() => {
    saveSimulationState(simState);
  }, [simState]);

  useEffect(() => {
    saveMemoryRecords(memories);
  }, [memories]);

  // Simulation timer loop
  useEffect(() => {
    if (!simState.isPlaying) return;

    const timer = setInterval(() => {
      setSimState((prev) => {
        const nextHour = (prev.currentHour + 1) % 24;
        return {
          ...prev,
          currentHour: nextHour,
        };
      });
      setIsApplied(false);
    }, simState.playbackSpeed);

    return () => clearInterval(timer);
  }, [simState.isPlaying, simState.playbackSpeed]);

  // Real-time calculations derived from current simulation state
  const regionalStates = useMemo(() => {
    return getRegionalStates(simState.currentHour, simState.tablets);
  }, [simState.currentHour, simState.tablets]);

  const clusterMetrics = useMemo(() => {
    return calculateClusterMetrics(
      simState.currentHour,
      simState.tablets,
      simState.latencyToleranceMs,
      simState.totalSavedCarbonAccumulatedG / 1000,
      memories
    );
  }, [simState.currentHour, simState.tablets, simState.latencyToleranceMs, simState.totalSavedCarbonAccumulatedG, memories]);

  const mekoDecision = useMemo(() => {
    return evaluateMekoOptimization(
      simState.currentHour,
      simState.tablets,
      simState.latencyToleranceMs,
      memories
    );
  }, [simState.currentHour, simState.tablets, simState.latencyToleranceMs, memories]);

  const timelineData = useMemo(() => {
    return generate24HourTimelineData(
      simState.tablets,
      simState.latencyToleranceMs,
      memories
    );
  }, [simState.tablets, simState.latencyToleranceMs, memories]);

  // =========================================================================
  // AUTONOMOUS DECISION-MAKING ENGINE (Meko Context + Gemini AI Decision)
  // When autonomousMode is TRUE, Meko evaluates grid emissions and peak times,
  // feeds the context to the underlying decision engine, and executes placement
  // immediately without asking the operator for approval.
  // =========================================================================
  useEffect(() => {
    if (!autonomousMode) return;

    // Check if decision is accepted with candidate leaders to relocate
    if (
      mekoDecision.status === 'ACCEPTED' &&
      mekoDecision.targetRegion &&
      mekoDecision.candidateTabletIds.length > 0
    ) {
      // Create a unique key for this decision state to prevent infinite loops
      const decisionKey = `${simState.currentHour}-${simState.latencyToleranceMs}-${mekoDecision.sourceRegion}-${mekoDecision.targetRegion}-${mekoDecision.candidateTabletIds.join(',')}`;

      if (decisionKey !== lastAutoAppliedKey) {
        // Check if any candidate tablet is not already in the target region
        const needsRelocation = simState.tablets.some(
          (t) =>
            mekoDecision.candidateTabletIds.includes(t.id) &&
            t.leaderRegion !== mekoDecision.targetRegion
        );

        if (needsRelocation) {
          const candidateIds = mekoDecision.candidateTabletIds;
          const target = mekoDecision.targetRegion;
          const source = mekoDecision.sourceRegion || 'mumbai';

          // Relocate the tablet leaders
          const updatedTablets = simState.tablets.map((t) => {
            if (candidateIds.includes(t.id)) {
              return { ...t, leaderRegion: target };
            }
            return t;
          });

          // Log autonomous decision with Meko context in persistent memory
          addMemoryRecord({
            simulatedHour: simState.currentHour,
            action: `AUTONOMOUS: Relocated ${candidateIds.length} Leaders: ${source.toUpperCase()} -> ${target.toUpperCase()}`,
            sourceRegion: source,
            targetRegion: target,
            leadersMoved: candidateIds.length,
            carbonSavedG: mekoDecision.carbonSavedG,
            latencyDeltaMs: mekoDecision.latencyDeltaMs,
            observedP99Ms: mekoDecision.projectedP99LatencyMs,
            outcome: 'SUCCESS',
            lessonText: `[AUTONOMOUS MEKO + GEMINI] Fed grid diurnal peak data at T+${simState.currentHour}:00 UTC. Sourced from high-carbon ${source.toUpperCase()} to clean-energy ${target.toUpperCase()}. Autonomously migrated ${candidateIds.length} tablet leaders saving ${mekoDecision.carbonSavedG}g CO2/hr (${mekoDecision.carbonSavedPercent}%) while restricting p99 latency impact to +${mekoDecision.latencyDeltaMs}ms within the ${simState.latencyToleranceMs}ms SLA. No human approval required.`,
            tags: ['autonomous', 'meko_context', 'gemini_ai', `${source}_to_${target}`],
          });

          setMemories(loadMemoryRecords());
          setSimState((prev) => ({
            ...prev,
            tablets: updatedTablets,
            totalSavedCarbonAccumulatedG: prev.totalSavedCarbonAccumulatedG + mekoDecision.carbonSavedG,
            lastAppliedHour: prev.currentHour,
          }));

          setLastAutoAppliedKey(decisionKey);
          setIsApplied(true);

          setAutoExecutionToast(
            `Meko + Gemini Autonomously Relocated ${candidateIds.length} Leaders to ${target.toUpperCase()} (Saved ${mekoDecision.carbonSavedG}g CO2/hr, +${mekoDecision.latencyDeltaMs}ms latency)`
          );
          const toastTimer = setTimeout(() => setAutoExecutionToast(null), 5000);
          return () => clearTimeout(toastTimer);
        }
      }
    }
  }, [
    autonomousMode,
    mekoDecision,
    simState.currentHour,
    simState.latencyToleranceMs,
    simState.tablets,
    lastAutoAppliedKey,
  ]);

  // Handlers
  const handleToleranceChange = (val: number) => {
    setSimState((prev) => ({
      ...prev,
      latencyToleranceMs: val,
    }));
    setIsApplied(false);
  };

  const handleHourChange = (hour: number) => {
    setSimState((prev) => ({
      ...prev,
      currentHour: hour,
    }));
    setIsApplied(false);
  };

  const handleTogglePlay = () => {
    setSimState((prev) => ({
      ...prev,
      isPlaying: !prev.isPlaying,
    }));
  };

  const handleNextHour = () => {
    setSimState((prev) => ({
      ...prev,
      currentHour: (prev.currentHour + 1) % 24,
    }));
    setIsApplied(false);
  };

  const handleReplay24h = () => {
    setSimState((prev) => ({
      ...prev,
      currentHour: 0,
      isPlaying: true,
      playbackSpeed: 1500,
    }));
    setIsApplied(false);
  };

  const handleResetSimulation = () => {
    setSimState((prev) => ({
      ...prev,
      currentHour: 12,
      isPlaying: false,
    }));
    setIsApplied(false);
  };

  const handleApplyOptimization = () => {
    if (mekoDecision.status !== 'ACCEPTED' || !mekoDecision.targetRegion) return;

    const candidateIds = mekoDecision.candidateTabletIds;
    const target = mekoDecision.targetRegion;
    const source = mekoDecision.sourceRegion || 'mumbai';

    // Update tablet placements
    const updatedTablets = simState.tablets.map((t) => {
      if (candidateIds.includes(t.id)) {
        return { ...t, leaderRegion: target };
      }
      return t;
    });

    // Record decision in Meko persistent memory
    addMemoryRecord({
      simulatedHour: simState.currentHour,
      action: `Relocated ${candidateIds.length} Leaders: ${source.toUpperCase()} -> ${target.toUpperCase()}`,
      sourceRegion: source,
      targetRegion: target,
      leadersMoved: candidateIds.length,
      carbonSavedG: mekoDecision.carbonSavedG,
      latencyDeltaMs: mekoDecision.latencyDeltaMs,
      observedP99Ms: mekoDecision.projectedP99LatencyMs,
      outcome: 'SUCCESS',
      lessonText: `Applied green shift at T+${simState.currentHour}:00 UTC. Reduced hourly carbon by ${mekoDecision.carbonSavedG}g (${mekoDecision.carbonSavedPercent}%) while keeping p99 latency increase to +${mekoDecision.latencyDeltaMs}ms within the ${simState.latencyToleranceMs}ms budget.`,
      tags: ['green_relocation', `${source}_to_${target}`, 'optimized'],
    });

    setMemories(loadMemoryRecords());

    setSimState((prev) => ({
      ...prev,
      tablets: updatedTablets,
      totalSavedCarbonAccumulatedG: prev.totalSavedCarbonAccumulatedG + mekoDecision.carbonSavedG,
      lastAppliedHour: prev.currentHour,
    }));

    setIsApplied(true);
  };

  const handleRebalanceEqual = () => {
    setSimState((prev) => ({
      ...prev,
      tablets: INITIAL_TABLETS,
    }));
    setLastAutoAppliedKey('');
    setIsApplied(false);
  };

  const handleResetMemory = () => {
    const cleared = clearMemoryRecords();
    setMemories(cleared);
  };

  const handleRestoreSeeds = () => {
    const restored = resetToSeedMemory();
    setMemories(restored);
  };

  const handleAddCustomIncident = (incident: Omit<MemoryRecord, 'id' | 'timestamp'>) => {
    addMemoryRecord(incident);
    setMemories(loadMemoryRecords());
  };

  // Scroll to section helper
  const handleNavigate = (sectionId: string) => {
    setActiveSection(sectionId);
    const el = document.getElementById(sectionId);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="min-h-screen bg-[#030712] text-zinc-100 flex flex-col font-sans selection:bg-emerald-500/20 selection:text-emerald-300">
      {/* Top Navigation */}
      <TopNav
        activeSection={activeSection}
        onNavigate={handleNavigate}
        onOpenJudgeDemo={() => setIsJudgeDemoOpen(true)}
        onOpenMethodology={() => setIsMethodologyOpen(true)}
        currentHour={simState.currentHour}
      />

      {/* Hero Header */}
      <section className="border-b border-zinc-800/80 bg-gradient-to-b from-zinc-950 via-zinc-900/60 to-[#030712] px-4 sm:px-6 lg:px-8 py-8 relative overflow-hidden">
        <div className="absolute top-0 right-1/4 w-96 h-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
          <div className="space-y-2.5 max-w-3xl">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-emerald-400 bg-emerald-950/60 border border-emerald-500/30 px-3 py-0.5 rounded-full shadow-sm flex items-center gap-1.5">
                <Bot className="w-3.5 h-3.5" />
                <span>Meko + Gemini Autonomous Database Optimizer</span>
              </span>
              <span className="text-xs font-mono text-zinc-400">
                YugabyteDB · 3 Clouds · RF=3
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-black tracking-tight text-white flex items-center gap-3">
              <span>CLOVER</span>
              <span className="text-xs font-mono font-normal px-2.5 py-1 rounded-md bg-emerald-900/50 text-emerald-300 border border-emerald-700/50">
                MEKO + GEMINI
              </span>
            </h1>
            <p className="text-sm sm:text-base text-zinc-300 font-medium">
              Autonomous Carbon-Aware Tablet Leader Placement for Distributed Databases.
            </p>
            <p className="text-xs text-zinc-400 leading-relaxed pt-0.5">
              Meko acts as the context tool fed with regional peak times, diurnal carbon emission profiles, and latency history. Gemini AI uses this context to make autonomous placement decisions without requiring manual human approval, shifting YugabyteDB leaders to cleaner grid energy while protecting strict p99 latency SLAs.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row md:flex-col gap-2.5 shrink-0">
            {/* Autonomous Mode Toggle */}
            <div className="flex items-center justify-between gap-3 bg-zinc-900/95 border border-zinc-700/80 rounded-xl p-3 text-xs shadow-lg backdrop-blur-md">
              <div className="flex items-center gap-2">
                <span className={`w-2.5 h-2.5 rounded-full ${autonomousMode ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-500'}`} />
                <span className="font-mono text-zinc-200 font-bold">
                  {autonomousMode ? 'AUTONOMOUS MODE: ON' : 'MANUAL APPROVAL: ON'}
                </span>
              </div>
              <button
                onClick={() => setAutonomousMode(!autonomousMode)}
                className={`px-2.5 py-1 text-[11px] font-bold rounded-lg transition-all cursor-pointer ${
                  autonomousMode
                    ? 'bg-emerald-500 text-zinc-950 hover:bg-emerald-400'
                    : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700 border border-zinc-700'
                }`}
              >
                {autonomousMode ? 'Zero-Approval' : 'Switch to Auto'}
              </button>
            </div>

            <button
              onClick={() => setIsJudgeDemoOpen(true)}
              className="flex items-center justify-center gap-2 px-5 py-3 text-xs font-bold text-zinc-950 bg-emerald-400 hover:bg-emerald-300 rounded-xl shadow-lg shadow-emerald-950/40 transition-all cursor-pointer hover:scale-[1.02]"
            >
              <Sparkles className="w-4 h-4 fill-zinc-950" />
              <span>START JUDGE DEMO (8 STEPS)</span>
            </button>

            <div className="flex items-center justify-between sm:justify-start gap-3 bg-zinc-900/90 border border-zinc-800 rounded-xl p-3 text-xs backdrop-blur-md">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
                <span className="font-mono text-zinc-300 font-semibold">
                  SIMULATION ACTIVE
                </span>
              </div>
              <span className="text-zinc-400 font-mono">
                T+{String(simState.currentHour).padStart(2, '0')}:00 UTC
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Autonomous Action Floating Notification */}
      {autoExecutionToast && (
        <div className="fixed bottom-6 right-6 z-50 max-w-md bg-emerald-950/95 border border-emerald-500/60 rounded-xl p-4 text-xs text-emerald-200 shadow-2xl backdrop-blur-md flex items-start gap-3 animate-bounce">
          <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <div className="font-bold text-emerald-300 flex items-center gap-1.5">
              <span>Meko Autonomous Execution Applied</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-900/80 text-emerald-300">
                Zero-Approval
              </span>
            </div>
            <p className="text-xs text-emerald-200/90 leading-relaxed">
              {autoExecutionToast}
            </p>
          </div>
        </div>
      )}

      {/* Main Viewport Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-10 flex-1 w-full">
        {/* KPI Cards Strip */}
        <section id="overview" className="scroll-mt-24 space-y-3">
          <KpiMetrics metrics={clusterMetrics} />
        </section>

        {/* Global Network Topology Map */}
        <section id="topology" className="scroll-mt-24 space-y-3">
          <NetworkTopologyMap
            regions={regionalStates}
            currentHour={simState.currentHour}
            activeDecision={mekoDecision}
          />
        </section>

        {/* 24-Hour Simulation Controls Toolbar */}
        <section className="space-y-3">
          <SimulationControls
            currentHour={simState.currentHour}
            isPlaying={simState.isPlaying}
            onTogglePlay={handleTogglePlay}
            onNextHour={handleNextHour}
            onReplay24h={handleReplay24h}
            onResetSimulation={handleResetSimulation}
            onHourChange={handleHourChange}
          />
        </section>

        {/* Regional Grid Monitors */}
        <section id="regions" className="scroll-mt-24 space-y-3">
          <RegionalMonitor
            regions={regionalStates}
            currentHour={simState.currentHour}
          />
        </section>

        {/* Meko AI Decision Engine & Interactive Latency Slider */}
        <section id="optimizer" className="scroll-mt-24 space-y-3">
          <MekoDecisionPanel
            decision={mekoDecision}
            latencyToleranceMs={simState.latencyToleranceMs}
            onToleranceChange={handleToleranceChange}
            onRunOptimization={() => setIsApplied(false)}
            onApplyOptimization={handleApplyOptimization}
            onRebalanceEqual={handleRebalanceEqual}
            isApplied={isApplied}
            autonomousMode={autonomousMode}
          />
        </section>

        {/* The Carbon-Performance Trade-off Dynamic Chart */}
        <section id="tradeoff" className="scroll-mt-24 space-y-3">
          <TradeoffChart
            timelineData={timelineData}
            currentHour={simState.currentHour}
            carbonPer1kTx={clusterMetrics.carbonPer1kTxG}
            onSelectHour={handleHourChange}
          />
        </section>

        {/* Meko Memory & Learning Section */}
        <section id="memory" className="scroll-mt-24 space-y-3">
          <MekoMemory
            memories={memories}
            onResetMemory={handleResetMemory}
            onRestoreSeeds={handleRestoreSeeds}
            onAddCustomIncident={handleAddCustomIncident}
          />
        </section>

        {/* YugabyteDB Cluster Architecture & Placement Topology */}
        <section id="cluster" className="scroll-mt-24 space-y-3">
          <YugabyteClusterView
            tablets={simState.tablets}
            currentHour={simState.currentHour}
          />
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-900 bg-[#030712] px-4 sm:px-6 lg:px-8 py-8 text-xs text-zinc-400">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-bold text-zinc-300">CLOVER</span>
            <span>·</span>
            <span>Context Engine: MEKO</span>
            <span>·</span>
            <span>Decision AI: Gemini</span>
            <span>·</span>
            <span className="text-emerald-400 font-mono">Autonomous Zero-Approval Placement</span>
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={() => setIsMethodologyOpen(true)}
              className="hover:text-zinc-300 transition-colors cursor-pointer"
            >
              Methodology & Formulas
            </button>
            <span>·</span>
            <button
              onClick={() => setIsJudgeDemoOpen(true)}
              className="text-emerald-400 hover:text-emerald-300 transition-colors cursor-pointer font-bold"
            >
              Run Judge Demo
            </button>
          </div>
        </div>
      </footer>

      {/* Modals */}
      <JudgeDemoModal
        isOpen={isJudgeDemoOpen}
        onClose={() => setIsJudgeDemoOpen(false)}
        onJumpToHour={handleHourChange}
        onSetTolerance={handleToleranceChange}
        onRunOptimization={() => setIsApplied(false)}
        onApplyOptimization={handleApplyOptimization}
        onNavigateSection={handleNavigate}
      />

      <MethodologyModal
        isOpen={isMethodologyOpen}
        onClose={() => setIsMethodologyOpen(false)}
      />
    </div>
  );
};

export default App;
