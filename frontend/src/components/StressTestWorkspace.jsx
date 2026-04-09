import { useState } from 'react';
import { evaluateReasoning } from '../api';
import StressTestResults from './StressTestResults';

function StressTestWorkspace() {
  const [problem, setProblem] = useState('');
  const [studentAnswer, setStudentAnswer] = useState('');
  const [confidence, setConfidence] = useState(50);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState('');
  const [results, setResults] = useState(null);

  const handleSubmit = async () => {
    if (!studentAnswer.trim()) {
      setError('Please enter a student answer to stress-test.');
      return;
    }

    setProcessing(true);
    setError('');
    setResults(null);

    try {
      const result = await evaluateReasoning(studentAnswer, problem, confidence);
      setResults(result);
    } catch (err) {
      setError(err.message || 'Stress test failed.');
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Input Form */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-2">
          <span className="text-2xl">🔬</span>
          <h2 className="text-lg font-semibold text-gray-900">Knowledge Stress-Test Engine</h2>
        </div>
        <p className="text-sm text-gray-500 mb-6">
          Submit a student answer to stress-test. The system will actively try to break the reasoning
          by generating adversarial scenarios, detecting failure points, and producing targeted challenge questions.
          This is NOT a tutoring tool — it is a reasoning stress-testing system.
        </p>

        {/* Problem (optional) */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Problem Statement <span className="text-gray-400 font-normal">(optional)</span>
          </label>
          <textarea
            value={problem}
            onChange={(e) => setProblem(e.target.value)}
            placeholder="Enter the problem or question the student was answering..."
            rows={3}
            className="w-full border border-gray-300 rounded-lg p-3 text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 resize-y"
            disabled={processing}
          />
        </div>

        {/* Student Answer (mandatory) */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Student Answer <span className="text-red-500">*</span>
          </label>
          <textarea
            value={studentAnswer}
            onChange={(e) => setStudentAnswer(e.target.value)}
            placeholder="Enter the student's answer, reasoning, or explanation to stress-test..."
            rows={6}
            className="w-full border border-gray-300 rounded-lg p-3 text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 resize-y"
            disabled={processing}
          />
        </div>

        {/* Confidence Slider */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Student Confidence: <span className="font-semibold text-purple-600">{confidence}%</span>
          </label>
          <input
            type="range"
            min="0"
            max="100"
            value={confidence}
            onChange={(e) => setConfidence(Number(e.target.value))}
            className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-purple-600"
            disabled={processing}
          />
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>0% — Not confident</span>
            <span>100% — Very confident</span>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="flex justify-end">
          <button
            onClick={handleSubmit}
            disabled={processing || !studentAnswer.trim()}
            className={`px-6 py-2.5 rounded-lg text-sm font-medium text-white transition-colors ${
              processing || !studentAnswer.trim()
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-purple-600 hover:bg-purple-700'
            }`}
          >
            {processing ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Stress Testing...
              </span>
            ) : (
              '⚡ Run Stress Test'
            )}
          </button>
        </div>
      </div>

      {/* Results */}
      {results && <StressTestResults results={results} />}
    </div>
  );
}

export default StressTestWorkspace;
