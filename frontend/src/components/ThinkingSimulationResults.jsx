function ThinkingSimulationResults({ results }) {
  if (!results) return null;

  const {
    cognitive_profiles = [],
    reasoning_graphs = [],
    strategy_distributions = [],
    structural_comparison = {},
    gap_analysis = [],
    student_graph = {},
    validation_passed = true,
    validation_notes = [],
  } = results;

  const levelColors = {
    beginner: {
      bg: 'bg-blue-50',
      border: 'border-blue-200',
      text: 'text-blue-800',
      badge: 'bg-blue-100 text-blue-800',
      accent: 'bg-blue-500',
    },
    intermediate: {
      bg: 'bg-amber-50',
      border: 'border-amber-200',
      text: 'text-amber-800',
      badge: 'bg-amber-100 text-amber-800',
      accent: 'bg-amber-500',
    },
    expert: {
      bg: 'bg-emerald-50',
      border: 'border-emerald-200',
      text: 'text-emerald-800',
      badge: 'bg-emerald-100 text-emerald-800',
      accent: 'bg-emerald-500',
    },
  };

  const levelIcons = {
    beginner: '🌱',
    intermediate: '🔧',
    expert: '🎯',
  };

  const abstractionColors = {
    LOW: { bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-300' },
    MEDIUM: { bg: 'bg-yellow-100', text: 'text-yellow-800', border: 'border-yellow-300' },
    HIGH: { bg: 'bg-purple-100', text: 'text-purple-800', border: 'border-purple-300' },
  };

  const strategyColors = {
    direct_application: 'bg-blue-100 text-blue-700',
    rule_based: 'bg-amber-100 text-amber-700',
    transformation: 'bg-purple-100 text-purple-700',
    reduction: 'bg-rose-100 text-rose-700',
    optimization: 'bg-emerald-100 text-emerald-700',
  };

  const relationIcons = {
    derives: '→',
    transforms: '⟹',
    simplifies: '↓',
  };

  const severityConfig = {
    info: { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-800', icon: 'ℹ️' },
    warning: { bg: 'bg-yellow-50', border: 'border-yellow-200', text: 'text-yellow-800', icon: '⚠️' },
    critical: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-800', icon: '🔴' },
  };

  const hasStudentGraph = student_graph && student_graph.student_level_match
    && student_graph.student_level_match !== 'unknown';

  return (
    <div className="space-y-6">
      {/* Validation Notes */}
      {!validation_passed && validation_notes.length > 0 && (
        <div className="bg-yellow-50 rounded-xl border border-yellow-200 p-4">
          <h4 className="text-sm font-semibold text-yellow-800 mb-2">⚠️ Validation Notes</h4>
          {validation_notes.map((note, i) => (
            <p key={i} className="text-xs text-yellow-700">{note}</p>
          ))}
        </div>
      )}

      {/* Cognitive Profiles with Constraint Rules */}
      {cognitive_profiles.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <span>🧠</span>
            Cognitive Profiles (Constraint Rules)
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {cognitive_profiles.map((profile, i) => {
              const colors = levelColors[profile.level] || levelColors.beginner;
              const icon = levelIcons[profile.level] || '📝';
              return (
                <div key={i} className={`rounded-lg border p-4 ${colors.bg} ${colors.border}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-lg">{icon}</span>
                    <span className={`px-2 py-0.5 text-xs font-semibold rounded-full ${colors.badge}`}>
                      {profile.level.charAt(0).toUpperCase() + profile.level.slice(1)}
                    </span>
                    <span className={`px-2 py-0.5 text-xs rounded-full ${(abstractionColors[profile.max_abstraction] || abstractionColors.LOW).bg} ${(abstractionColors[profile.max_abstraction] || abstractionColors.LOW).text}`}>
                      Max: {profile.max_abstraction}
                    </span>
                  </div>
                  <p className={`text-sm mb-3 ${colors.text}`}>{profile.description}</p>
                  {profile.allowed_operations && profile.allowed_operations.length > 0 && (
                    <div className="mb-2">
                      <span className="text-xs font-medium text-gray-600">Allowed:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {profile.allowed_operations.map((op, j) => (
                          <span key={j} className="text-xs px-1.5 py-0.5 bg-green-100 text-green-700 rounded">
                            {op.replace(/_/g, ' ')}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {profile.forbidden_operations && profile.forbidden_operations.length > 0 && (
                    <div>
                      <span className="text-xs font-medium text-gray-600">Forbidden:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {profile.forbidden_operations.map((op, j) => (
                          <span key={j} className="text-xs px-1.5 py-0.5 bg-red-100 text-red-700 rounded">
                            {op.replace(/_/g, ' ')}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Reasoning Graphs with Nodes, Edges, Abstraction */}
      {reasoning_graphs.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <span>🔀</span>
            Reasoning Graphs
          </h3>
          <div className="space-y-6">
            {reasoning_graphs.map((graph, i) => {
              const colors = levelColors[graph.level] || levelColors.beginner;
              const icon = levelIcons[graph.level] || '📝';
              const nodes = graph.nodes || [];
              const edges = graph.edges || [];
              const decisions = graph.decisions || [];
              const absMetrics = graph.abstraction_metrics || {};
              return (
                <div key={i} className={`rounded-lg border p-4 ${colors.bg} ${colors.border}`}>
                  <div className="flex items-center gap-2 mb-4 flex-wrap">
                    <span className="text-lg">{icon}</span>
                    <span className={`px-2 py-0.5 text-xs font-semibold rounded-full ${colors.badge}`}>
                      {graph.level.charAt(0).toUpperCase() + graph.level.slice(1)} Graph
                    </span>
                    <span className="text-xs text-gray-500">
                      {nodes.length} node{nodes.length !== 1 ? 's' : ''} · {edges.length} edge{edges.length !== 1 ? 's' : ''}
                    </span>
                    {absMetrics.max_abstraction && (
                      <span className={`px-2 py-0.5 text-xs rounded-full ${(abstractionColors[absMetrics.max_abstraction] || abstractionColors.LOW).bg} ${(abstractionColors[absMetrics.max_abstraction] || abstractionColors.LOW).text}`}>
                        Max Abstraction: {absMetrics.max_abstraction}
                      </span>
                    )}
                  </div>

                  {/* Nodes */}
                  <div className="space-y-2">
                    {nodes.map((node, j) => {
                      const absColor = abstractionColors[node.abstraction_level] || abstractionColors.LOW;
                      const stratColor = strategyColors[node.strategy_type] || 'bg-gray-100 text-gray-700';
                      // Find outgoing edge for this node
                      const outEdge = edges.find(e => e.from_step_id === node.step_id);
                      return (
                        <div key={j}>
                          <div className={`bg-white rounded-lg p-3 border shadow-sm ${absColor.border}`}>
                            <div className="flex items-center gap-2 mb-2 flex-wrap">
                              <div className={`w-6 h-6 rounded-full ${colors.accent} text-white text-xs flex items-center justify-center font-bold shrink-0`}>
                                {j + 1}
                              </div>
                              <span className="text-sm font-medium text-gray-900">
                                {node.operation_type.replace(/_/g, ' ')}
                              </span>
                              {node.concept_used && (
                                <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full">
                                  {node.concept_used}
                                </span>
                              )}
                              <span className={`text-xs px-2 py-0.5 rounded-full ${absColor.bg} ${absColor.text}`}>
                                {node.abstraction_level}
                              </span>
                              <span className={`text-xs px-2 py-0.5 rounded-full ${stratColor}`}>
                                {node.strategy_type.replace(/_/g, ' ')}
                              </span>
                            </div>
                            {(node.input_value || node.output_value) && (
                              <div className="text-xs text-gray-600 ml-8 mb-1">
                                {node.input_value && <span className="block"><span className="font-medium">Input:</span> {node.input_value}</span>}
                                {node.output_value && <span className="block"><span className="font-medium">Output:</span> {node.output_value}</span>}
                              </div>
                            )}
                            {node.reasoning && (
                              <p className="text-xs text-gray-500 ml-8 italic">{node.reasoning}</p>
                            )}
                          </div>
                          {/* Edge connector */}
                          {outEdge && (
                            <div className="flex items-center justify-center py-1">
                              <span className="text-xs text-gray-400 font-mono">
                                {relationIcons[outEdge.relation_type] || '→'} {outEdge.relation_type}
                              </span>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {/* Decisions */}
                  {decisions.length > 0 && (
                    <div className="mt-4 pt-3 border-t border-gray-200">
                      <h5 className="text-xs font-semibold text-gray-600 mb-2">Decision Points</h5>
                      <div className="space-y-2">
                        {decisions.map((d, j) => (
                          <div key={j} className="text-xs bg-white/60 rounded p-2 border border-gray-100">
                            <span className="font-medium text-gray-700">🔹 {d.decision_point}</span>
                            {d.alternatives_considered && d.alternatives_considered.length > 0 && (
                              <span className="text-gray-500 ml-2">
                                (considered: {d.alternatives_considered.join(', ')})
                              </span>
                            )}
                            {d.chosen_path_reason && (
                              <p className="text-gray-500 mt-0.5 italic">↳ {d.chosen_path_reason}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Strategy Distributions with Percentages */}
      {strategy_distributions.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <span>📊</span>
            Strategy Distributions
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {strategy_distributions.map((dist, i) => {
              const colors = levelColors[dist.level] || levelColors.beginner;
              const bars = [
                { label: 'Direct', pct: dist.direct_application_pct || 0, color: 'bg-blue-400' },
                { label: 'Rule-based', pct: dist.rule_based_pct || 0, color: 'bg-amber-400' },
                { label: 'Transform', pct: dist.transformation_pct || 0, color: 'bg-purple-400' },
                { label: 'Reduction', pct: dist.reduction_pct || 0, color: 'bg-rose-400' },
                { label: 'Optimize', pct: dist.optimization_pct || 0, color: 'bg-emerald-400' },
              ].filter(b => b.pct > 0);
              return (
                <div key={i} className={`rounded-lg border p-4 ${colors.bg} ${colors.border}`}>
                  <span className={`text-sm font-semibold ${colors.text}`}>
                    {dist.level.charAt(0).toUpperCase() + dist.level.slice(1)}
                  </span>
                  <div className="mt-3 space-y-2">
                    {bars.map((bar, j) => (
                      <div key={j}>
                        <div className="flex justify-between text-xs text-gray-600 mb-0.5">
                          <span>{bar.label}</span>
                          <span>{bar.pct}%</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div className={`h-2 rounded-full ${bar.color}`} style={{ width: `${bar.pct}%` }} />
                        </div>
                      </div>
                    ))}
                    {bars.length === 0 && (
                      <p className="text-xs text-gray-400 italic">No strategy data</p>
                    )}
                  </div>
                  {dist.strategies_used && dist.strategies_used.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-3">
                      {dist.strategies_used.map((tag, j) => (
                        <span key={j} className={`px-2 py-0.5 text-xs rounded-full ${strategyColors[tag] || 'bg-gray-100 text-gray-700'}`}>
                          {tag.replace(/_/g, ' ')}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Structural Comparison */}
      {structural_comparison && Object.keys(structural_comparison).length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <span>🔬</span>
            Structural Comparison
          </h3>

          {/* Graph Shape */}
          {structural_comparison.graph_shape && Object.keys(structural_comparison.graph_shape).length > 0 && (
            <div className="mb-6">
              <h4 className="text-sm font-semibold text-gray-700 mb-3">Graph Shape</h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {Object.entries(structural_comparison.graph_shape).map(([level, data]) => {
                  const colors = levelColors[level] || levelColors.beginner;
                  return (
                    <div key={level} className={`rounded-lg border p-3 ${colors.bg} ${colors.border}`}>
                      <span className={`text-sm font-medium ${colors.text}`}>
                        {level.charAt(0).toUpperCase() + level.slice(1)}
                      </span>
                      <div className="mt-2 space-y-1">
                        <div className="text-xs text-gray-600">
                          <span className="font-medium">Nodes:</span> {data.node_count}
                        </div>
                        <div className="text-xs text-gray-600">
                          <span className="font-medium">Edges:</span> {data.edge_count}
                        </div>
                        <div className="text-xs text-gray-600">
                          <span className="font-medium">Depth:</span> {data.depth}
                        </div>
                        <div className="text-xs text-gray-600">
                          <span className="font-medium">Approach:</span>{' '}
                          {data.is_linear ? 'Linear' : 'Transformed'}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Abstraction Flow */}
          {structural_comparison.abstraction_flow && Object.keys(structural_comparison.abstraction_flow).length > 0 && (
            <div className="mb-6">
              <h4 className="text-sm font-semibold text-gray-700 mb-3">Abstraction Flow</h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {Object.entries(structural_comparison.abstraction_flow).map(([level, data]) => {
                  const colors = levelColors[level] || levelColors.beginner;
                  const flow = data.flow || [];
                  return (
                    <div key={level} className={`rounded-lg border p-3 ${colors.bg} ${colors.border}`}>
                      <span className={`text-sm font-medium ${colors.text}`}>
                        {level.charAt(0).toUpperCase() + level.slice(1)}
                      </span>
                      <div className="mt-2 space-y-1">
                        <div className="text-xs text-gray-600">
                          <span className="font-medium">Avg:</span> {data.average_abstraction}
                        </div>
                        <div className="text-xs text-gray-600">
                          <span className="font-medium">Max:</span>{' '}
                          <span className={`px-1.5 py-0.5 rounded ${(abstractionColors[data.max_abstraction] || abstractionColors.LOW).bg} ${(abstractionColors[data.max_abstraction] || abstractionColors.LOW).text}`}>
                            {data.max_abstraction}
                          </span>
                        </div>
                        {flow.length > 0 && (
                          <div className="flex gap-1 mt-1 flex-wrap">
                            {flow.map((lvl, k) => (
                              <span key={k} className={`text-xs px-1.5 py-0.5 rounded ${(abstractionColors[lvl] || abstractionColors.LOW).bg} ${(abstractionColors[lvl] || abstractionColors.LOW).text}`}>
                                {lvl}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Key Differences */}
          {structural_comparison.key_differences && structural_comparison.key_differences.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-gray-700 mb-3">Key Structural Differences</h4>
              <div className="space-y-2">
                {structural_comparison.key_differences.map((diff, i) => (
                  <div key={i} className="p-3 bg-gray-50 rounded-lg text-sm text-gray-700 flex items-start gap-2">
                    <span className="font-bold text-indigo-500 mt-0.5">→</span>
                    <span>{diff}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Student Graph */}
      {hasStudentGraph && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <span>👤</span>
            Student Reasoning Graph
          </h3>
          <div className="space-y-4">
            {/* Level match */}
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-600">Your reasoning matches:</span>
              <span className={`px-3 py-1 text-sm font-semibold rounded-full ${
                (levelColors[student_graph.student_level_match] || levelColors.beginner).badge
              }`}>
                {student_graph.student_level_match.charAt(0).toUpperCase() +
                 student_graph.student_level_match.slice(1)} Level
              </span>
            </div>

            {/* Student nodes visualization */}
            {student_graph.nodes && student_graph.nodes.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">Your Reasoning Steps</h4>
                <div className="space-y-2">
                  {student_graph.nodes.map((node, j) => {
                    const absColor = abstractionColors[node.abstraction_level] || abstractionColors.LOW;
                    const stratColor = strategyColors[node.strategy_type] || 'bg-gray-100 text-gray-700';
                    const outEdge = (student_graph.edges || []).find(e => e.from_step_id === node.step_id);
                    return (
                      <div key={j}>
                        <div className={`bg-gray-50 rounded-lg p-3 border ${absColor.border}`}>
                          <div className="flex items-center gap-2 flex-wrap">
                            <div className="w-5 h-5 rounded-full bg-gray-500 text-white text-xs flex items-center justify-center font-bold shrink-0">
                              {j + 1}
                            </div>
                            <span className="text-sm font-medium text-gray-900">
                              {node.operation_type.replace(/_/g, ' ')}
                            </span>
                            <span className={`text-xs px-2 py-0.5 rounded-full ${absColor.bg} ${absColor.text}`}>
                              {node.abstraction_level}
                            </span>
                            <span className={`text-xs px-2 py-0.5 rounded-full ${stratColor}`}>
                              {node.strategy_type.replace(/_/g, ' ')}
                            </span>
                          </div>
                        </div>
                        {outEdge && (
                          <div className="flex items-center justify-center py-0.5">
                            <span className="text-xs text-gray-400 font-mono">
                              {relationIcons[outEdge.relation_type] || '→'}
                            </span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Student abstraction metrics */}
            {student_graph.abstraction_metrics && (
              <div className="flex gap-4 text-xs text-gray-600">
                <span><span className="font-medium">Avg Abstraction:</span> {student_graph.abstraction_metrics.average_abstraction}</span>
                <span><span className="font-medium">Max:</span> {student_graph.abstraction_metrics.max_abstraction}</span>
              </div>
            )}

            {/* Missing nodes */}
            {student_graph.missing_nodes && student_graph.missing_nodes.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">Missing Nodes</h4>
                <div className="space-y-1">
                  {student_graph.missing_nodes.map((step, j) => (
                    <div key={j} className="p-2 bg-yellow-50 border border-yellow-200 rounded text-sm text-yellow-800">
                      ⚠️ {step}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Missing transformations */}
            {student_graph.missing_transformations && student_graph.missing_transformations.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">Missing Transformations</h4>
                <div className="flex flex-wrap gap-2">
                  {student_graph.missing_transformations.map((t, j) => (
                    <span key={j} className="px-2 py-1 text-xs bg-red-50 text-red-700 border border-red-200 rounded-full">
                      {t.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Unnecessary steps */}
            {student_graph.unnecessary_steps && student_graph.unnecessary_steps.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">Unnecessary Steps</h4>
                <div className="space-y-1">
                  {student_graph.unnecessary_steps.map((ineff, j) => (
                    <div key={j} className="p-2 bg-orange-50 border border-orange-200 rounded text-sm text-orange-800">
                      {ineff}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Abstraction mismatches */}
            {student_graph.abstraction_mismatches && student_graph.abstraction_mismatches.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">Abstraction Mismatches</h4>
                <div className="space-y-1">
                  {student_graph.abstraction_mismatches.map((gap, j) => (
                    <div key={j} className="p-2 bg-red-50 border border-red-200 rounded text-sm text-red-800">
                      🔴 {gap}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Gap Analysis */}
      {gap_analysis.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <span>🔍</span>
            Structural Gap Analysis
          </h3>
          <div className="space-y-2">
            {gap_analysis.map((gap, i) => {
              const config = severityConfig[gap.severity] || severityConfig.info;
              const sourceLabel = gap.source ? ` [${gap.source}]` : '';
              return (
                <div
                  key={i}
                  className={`p-3 rounded-lg border text-sm ${config.bg} ${config.border} ${config.text}`}
                >
                  <span className="mr-2">{config.icon}</span>
                  {gap.insight}
                  <span className="text-xs opacity-60 ml-2">{sourceLabel}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default ThinkingSimulationResults;
