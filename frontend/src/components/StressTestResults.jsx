function StressTestResults({ results }) {
  if (!results) return null;

  const {
    stress_test_results = [],
    weakness_summary = [],
    robustness_summary = {},
    adversarial_questions = [],
  } = results;

  const levelConfig = {
    high: { color: 'bg-green-100 text-green-800 border-green-200', label: 'High' },
    medium: { color: 'bg-yellow-100 text-yellow-800 border-yellow-200', label: 'Medium' },
    low: { color: 'bg-red-100 text-red-800 border-red-200', label: 'Low' },
    unknown: { color: 'bg-gray-100 text-gray-800 border-gray-200', label: 'Unknown' },
  };

  const robustnessLevel = levelConfig[robustness_summary.level] || levelConfig.unknown;
  const scorePercent = Math.round((robustness_summary.robustness_score || 0) * 100);

  return (
    <div className="space-y-6">
      {/* Robustness Summary */}
      <div className={`rounded-xl border p-5 ${robustnessLevel.color}`}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold">Robustness Score</h3>
          <div className="flex items-center gap-3">
            <span className={`px-3 py-1 text-sm font-semibold rounded-full ${robustnessLevel.color}`}>
              {robustnessLevel.label}
            </span>
            <div className="text-2xl font-bold">{scorePercent}%</div>
          </div>
        </div>
        {/* Progress bar */}
        <div className="w-full bg-white/50 rounded-full h-3 mb-2">
          <div
            className={`h-3 rounded-full transition-all duration-500 ${
              robustness_summary.level === 'high'
                ? 'bg-green-500'
                : robustness_summary.level === 'medium'
                ? 'bg-yellow-500'
                : 'bg-red-500'
            }`}
            style={{ width: `${scorePercent}%` }}
          />
        </div>
        <p className="text-sm">{robustness_summary.summary}</p>
      </div>

      {/* Stress Test Results */}
      {stress_test_results.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <span className="text-red-500">⚡</span>
            Stress Test Results
          </h3>
          <div className="space-y-2">
            {stress_test_results.map((result, i) => {
              const isFail = result.startsWith('FAILS');
              return (
                <div
                  key={i}
                  className={`p-3 rounded-lg text-sm ${
                    isFail
                      ? 'bg-red-50 border border-red-200 text-red-800'
                      : 'bg-green-50 border border-green-200 text-green-800'
                  }`}
                >
                  <span className="font-medium">{isFail ? '✗' : '✓'}</span>{' '}
                  {result}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Weakness Summary */}
      {weakness_summary.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <span className="text-orange-500">⚠</span>
            Weakness Analysis
          </h3>
          <div className="space-y-3">
            {weakness_summary.map((weakness, i) => (
              <div key={i} className="flex items-start gap-3 p-3 bg-orange-50 rounded-lg border border-orange-200">
                <span className="px-2 py-0.5 text-xs font-medium bg-orange-100 text-orange-800 rounded-full whitespace-nowrap mt-0.5">
                  {weakness.type.replace('_', ' ')}
                </span>
                <p className="text-sm text-gray-800">{weakness.detail}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Adversarial Questions */}
      {adversarial_questions.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <span className="text-purple-500">❓</span>
            Challenge Questions
          </h3>
          <p className="text-xs text-gray-500 mb-3">
            These questions target identified weaknesses in your reasoning. No answers provided — think carefully.
          </p>
          <div className="space-y-2">
            {adversarial_questions.map((question, i) => (
              <div
                key={i}
                className="p-3 bg-purple-50 border border-purple-200 rounded-lg text-sm text-purple-900 flex items-start gap-2"
              >
                <span className="font-bold text-purple-600 mt-0.5">{i + 1}.</span>
                <span>{question}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default StressTestResults;
