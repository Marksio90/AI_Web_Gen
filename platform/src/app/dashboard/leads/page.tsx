"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

interface Lead {
  id: string;
  name: string;
  city: string;
  category: string;
  stage: string;
  websiteStatus: string;
  email?: string;
  phone?: string;
  demoSiteUrl?: string;
  qcScore?: number;
  rating?: number;
  reviewCount?: number;
  outreachSentAt?: string;
  lastActivityAt?: string;
  createdAt: string;
}

interface Pagination {
  page: number;
  limit: number;
  total: number;
  pages: number;
}

const STAGE_LABELS: Record<string, { label: string; color: string }> = {
  DISCOVERED:     { label: "Odkryty",         color: "bg-gray-100 text-gray-700" },
  ANALYZED:       { label: "Przeanalizowany", color: "bg-blue-100 text-blue-700" },
  SITE_GENERATED: { label: "Strona gotowa",   color: "bg-green-100 text-green-700" },
  OUTREACH_SENT:  { label: "Email wysłany",   color: "bg-amber-100 text-amber-700" },
  OPENED:         { label: "Otwarty",         color: "bg-orange-100 text-orange-700" },
  REPLIED:        { label: "Odpowiedź",       color: "bg-purple-100 text-purple-700" },
  DEMO_VIEWED:    { label: "Demo obejrzane",  color: "bg-teal-100 text-teal-700" },
  CONVERTED:      { label: "Klient",          color: "bg-emerald-100 text-emerald-700" },
  LOST:           { label: "Utracony",        color: "bg-red-100 text-red-700" },
};

const CATEGORY_LABELS: Record<string, string> = {
  RESTAURANT: "Restauracja", BEAUTY_SALON: "Salon urody", DENTAL_CLINIC: "Dentysta",
  AUTO_REPAIR: "Warsztat", LAW_OFFICE: "Kancelaria", PLUMBER: "Hydraulik",
  FITNESS: "Siłownia", PHARMACY: "Apteka", HOTEL: "Hotel", BAKERY: "Piekarnia",
  FLORIST: "Kwiaciarnia", ACCOUNTANT: "Księgowość", PHYSIOTHERAPY: "Fizjoterapia",
  OPTICIAN: "Optyk", OTHER: "Inne",
};

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pagination, setPagination] = useState<Pagination>({ page: 1, limit: 50, total: 0, pages: 0 });
  const [search, setSearch] = useState("");
  const [stage, setStage] = useState("");
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const router = useRouter();

  const fetchLeads = useCallback(async (page = 1) => {
    // Cancel previous request
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (stage) params.set("stage", stage);
    params.set("page", String(page));
    params.set("limit", "50");

    try {
      const resp = await fetch(`/api/leads?${params}`, { signal: controller.signal });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setLeads(data.leads || []);
      setPagination(data.pagination || { page: 1, limit: 50, total: 0, pages: 0 });
    } catch (err) {
      if (err instanceof Error && err.name !== "AbortError") {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [search, stage]);

  useEffect(() => {
    fetchLeads();
    return () => abortRef.current?.abort();
  }, [fetchLeads]);

  async function handleGenerate(leadId: string) {
    if (generatingId) return;
    setGeneratingId(leadId);
    try {
      const resp = await fetch(`/api/leads/${leadId}/generate`, { method: "POST" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      if (data.success) {
        fetchLeads(pagination.page);
      } else {
        setError(`Generowanie nie powiodlo sie: ${data.error}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Blad generowania");
    } finally {
      setGeneratingId(null);
    }
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Leady</h1>
          <p className="text-gray-500 mt-1">{pagination.total.toLocaleString("pl")} firm w bazie</p>
        </div>
        <button
          onClick={() => router.push("/dashboard/campaigns/new")}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
        >
          + Nowa kampania
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center justify-between">
          <p className="text-red-700 text-sm">{error}</p>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600 text-sm">Zamknij</button>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 mb-6">
        <input
          type="search"
          placeholder="Szukaj firm..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && fetchLeads()}
          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <select
          value={stage}
          onChange={(e) => setStage(e.target.value)}
          className="px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="">Wszystkie etapy</option>
          {Object.entries(STAGE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v.label}</option>
          ))}
        </select>
        <button
          onClick={() => fetchLeads()}
          className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition-colors"
        >
          Filtruj
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Firma</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Kategoria</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Etap</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Kontakt</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Strona</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Akcje</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {leads.map((lead) => {
                  const stageInfo = STAGE_LABELS[lead.stage] || { label: lead.stage, color: "bg-gray-100 text-gray-700" };
                  return (
                    <tr key={lead.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-900">{lead.name}</p>
                        <p className="text-gray-500 text-xs">{lead.city}</p>
                      </td>
                      <td className="px-4 py-3 text-gray-600">
                        {CATEGORY_LABELS[lead.category] || lead.category}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${stageInfo.color}`}>
                          {stageInfo.label}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="space-y-1">
                          {lead.email && (
                            <p className="text-xs text-gray-600 truncate max-w-[160px]">{lead.email}</p>
                          )}
                          {lead.phone && (
                            <p className="text-xs text-gray-500">{lead.phone}</p>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {lead.demoSiteUrl ? (
                          <div className="flex items-center gap-2">
                            <a
                              href={lead.demoSiteUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-indigo-600 hover:underline text-xs"
                            >
                              Demo
                            </a>
                            {lead.qcScore != null && (
                              <span className={`text-xs font-medium ${lead.qcScore >= 75 ? "text-green-600" : "text-amber-600"}`}>
                                {lead.qcScore}/100
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-gray-400 text-xs">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          {!lead.demoSiteUrl && (
                            <button
                              onClick={() => handleGenerate(lead.id)}
                              disabled={generatingId === lead.id}
                              className="px-3 py-1 bg-indigo-600 text-white rounded text-xs font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                            >
                              {generatingId === lead.id ? "Generuje..." : "Generuj"}
                            </button>
                          )}
                          <button
                            onClick={() => router.push(`/dashboard/leads/${lead.id}`)}
                            className="px-3 py-1 bg-gray-100 text-gray-700 rounded text-xs font-medium hover:bg-gray-200 transition-colors"
                          >
                            Szczegoly
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {leads.length === 0 && !error && (
              <div className="text-center py-12 text-gray-400">
                Brak leadow. Uruchom crawler aby znalezc firmy.
              </div>
            )}
          </div>
        )}
      </div>

      {/* Pagination controls */}
      {pagination.pages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-gray-500">
            Strona {pagination.page} z {pagination.pages}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => fetchLeads(pagination.page - 1)}
              disabled={pagination.page <= 1}
              className="px-3 py-1 bg-gray-100 text-gray-700 rounded text-sm font-medium hover:bg-gray-200 disabled:opacity-50 transition-colors"
            >
              Poprzednia
            </button>
            <button
              onClick={() => fetchLeads(pagination.page + 1)}
              disabled={pagination.page >= pagination.pages}
              className="px-3 py-1 bg-gray-100 text-gray-700 rounded text-sm font-medium hover:bg-gray-200 disabled:opacity-50 transition-colors"
            >
              Nastepna
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
