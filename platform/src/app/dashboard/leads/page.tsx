"use client";

import { useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";

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
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [stage, setStage] = useState("");
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const router = useRouter();

  const fetchLeads = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (stage) params.set("stage", stage);
    params.set("limit", "50");

    const resp = await fetch(`/api/leads?${params}`);
    const data = await resp.json();
    setLeads(data.leads || []);
    setTotal(data.pagination?.total || 0);
    setLoading(false);
  }, [search, stage]);

  useState(() => {
    fetchLeads();
  });

  async function handleGenerate(leadId: string) {
    setGeneratingId(leadId);
    try {
      const resp = await fetch(`/api/leads/${leadId}/generate`, { method: "POST" });
      const data = await resp.json();
      if (data.success) {
        alert(`Strona wygenerowana: ${data.demoSiteUrl}`);
        fetchLeads();
      } else {
        alert(`Błąd: ${data.error}`);
      }
    } finally {
      setGeneratingId(null);
    }
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Leady</h1>
          <p className="text-gray-500 mt-1">{total.toLocaleString("pl")} firm w bazie</p>
        </div>
        <button
          onClick={() => router.push("/dashboard/campaigns/new")}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors"
        >
          + Nowa kampania
        </button>
      </div>

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
          onChange={(e) => { setStage(e.target.value); fetchLeads(); }}
          className="px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="">Wszystkie etapy</option>
          {Object.entries(STAGE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v.label}</option>
          ))}
        </select>
        <button
          onClick={fetchLeads}
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
                              Demo →
                            </a>
                            {lead.qcScore && (
                              <span className={`text-xs font-medium ${lead.qcScore >= 75 ? "text-green-600" : "text-amber-600"}`}>
                                {lead.qcScore}/100
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-gray-400 text-xs">—</span>
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
                              {generatingId === lead.id ? "..." : "Generuj"}
                            </button>
                          )}
                          <button
                            onClick={() => router.push(`/dashboard/leads/${lead.id}`)}
                            className="px-3 py-1 bg-gray-100 text-gray-700 rounded text-xs font-medium hover:bg-gray-200 transition-colors"
                          >
                            Szczegóły
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {leads.length === 0 && (
              <div className="text-center py-12 text-gray-400">
                Brak leadów. Uruchom crawler aby znaleźć firmy.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
