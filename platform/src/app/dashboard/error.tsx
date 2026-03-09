"use client";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-6">
      <div className="bg-white rounded-xl border border-red-200 p-8 max-w-md text-center">
        <p className="text-4xl mb-4">!</p>
        <h2 className="text-xl font-bold text-gray-900 mb-2">Cos poszlo nie tak</h2>
        <p className="text-gray-500 text-sm mb-6">
          {error.message || "Wystapil nieoczekiwany blad. Sprobuj ponownie."}
        </p>
        <button
          onClick={reset}
          className="px-6 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
        >
          Sprobuj ponownie
        </button>
      </div>
    </div>
  );
}
