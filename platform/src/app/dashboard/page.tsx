"use client";

import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";

interface DashboardStats {
  totalLeads: number;
  sitesGenerated: number;
  emailsSent: number;
  conversions: number;
  conversionRate: string;
  stageBreakdown: Array<{ stage: string; count: number }>;
  categoryBreakdown: Array<{ category: string; count: number }>;
  recentActivity: Array<{ id: string; leadName: string; type: string; createdAt: string }>;
  monthlyCost: { openai: number; groq: number; total: number };
}

const STAGE_COLORS: Record<string, string> = {
  DISCOVERED: "#94a3b8",
  ANALYZED: "#60a5fa",
  SITE_GENERATED: "#34d399",
  OUTREACH_SENT: "#f59e0b",
  OPENED: "#fb923c",
  REPLIED: "#a78bfa",
  DEMO_VIEWED: "#2dd4bf",
  CONVERTED: "#22c55e",
  LOST: "#f87171",
};

const ACTIVITY_LABELS: Record<string, string> = {
  DISCOVERED: "Odkryto firmę",
  SEO_ANALYZED: "Analiza SEO",
  SITE_GENERATED: "Wygenerowano stronę",
  EMAIL_SENT: "Wysłano email",
  EMAIL_OPENED: "Email otwarty",
  SUBSCRIBED: "Nowy klient",
  UNSUBSCRIBED: "Wypisanie",
};

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/dashboard/stats")
      .then((r) => r.json())
      .then(setStats)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600" />
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500 mt-1">Przegląd platformy AI Web Generator</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard title="Wszystkie leady" value={stats.totalLeads.toLocaleString("pl")} icon="🎯" color="blue" />
        <KPICard title="Strony wygenerowane" value={stats.sitesGenerated.toLocaleString("pl")} icon="🌐" color="green" />
        <KPICard title="Emaile wysłane" value={stats.emailsSent.toLocaleString("pl")} icon="📧" color="amber" />
        <KPICard
          title="Konwersje"
          value={stats.conversions.toLocaleString("pl")}
          subtitle={`${stats.conversionRate}% współczynnik`}
          icon="💎"
          color="purple"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pipeline stages */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Lejek sprzedażowy</h2>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={stats.stageBreakdown} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis type="category" dataKey="stage" tick={{ fontSize: 11 }} width={120} />
              <Tooltip />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {stats.stageBreakdown.map((entry, i) => (
                  <Cell key={i} fill={STAGE_COLORS[entry.stage] || "#6366f1"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Category breakdown */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Kategorie firm</h2>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={stats.categoryBreakdown}
                dataKey="count"
                nameKey="category"
                cx="50%"
                cy="50%"
                outerRadius={80}
                label={({ category, percent }) => `${category} ${(percent * 100).toFixed(0)}%`}
              >
                {stats.categoryBreakdown.map((_, i) => (
                  <Cell key={i} fill={`hsl(${(i * 47) % 360}, 65%, 55%)`} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent activity */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Ostatnia aktywność</h2>
          <div className="space-y-3">
            {stats.recentActivity.map((activity) => (
              <div key={activity.id} className="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0">
                <div className="w-8 h-8 rounded-full bg-indigo-50 flex items-center justify-center text-xs">
                  {activity.type === "SUBSCRIBED" ? "💎" :
                   activity.type === "EMAIL_SENT" ? "📧" :
                   activity.type === "SITE_GENERATED" ? "🌐" : "🎯"}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{activity.leadName}</p>
                  <p className="text-xs text-gray-500">{ACTIVITY_LABELS[activity.type] || activity.type}</p>
                </div>
                <p className="text-xs text-gray-400 flex-shrink-0">
                  {new Date(activity.createdAt).toLocaleDateString("pl-PL")}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Cost tracker */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Koszty (ten miesiąc)</h2>
          <div className="space-y-4">
            <CostRow label="OpenAI API" amount={stats.monthlyCost.openai} currency="$" />
            <CostRow label="Groq API" amount={stats.monthlyCost.groq} currency="$" />
            <div className="border-t pt-4">
              <CostRow
                label="Łącznie"
                amount={stats.monthlyCost.total}
                currency="$"
                bold
              />
              <p className="text-xs text-gray-400 mt-2">
                ≈ {(stats.monthlyCost.total * 4.0).toFixed(0)} PLN przy kursie 4.0 PLN/$
              </p>
            </div>
          </div>

          <div className="mt-6 p-3 bg-green-50 rounded-lg">
            <p className="text-xs text-green-700 font-medium">
              Budżet miesięczny: ~$125 / 500 PLN
            </p>
            <div className="w-full bg-green-200 rounded-full h-2 mt-2">
              <div
                className="bg-green-600 h-2 rounded-full"
                style={{ width: `${Math.min((stats.monthlyCost.total / 125) * 100, 100)}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function KPICard({
  title, value, subtitle, icon, color,
}: {
  title: string; value: string; subtitle?: string; icon: string; color: string;
}) {
  const colorMap = {
    blue: "bg-blue-50 text-blue-600",
    green: "bg-green-50 text-green-600",
    amber: "bg-amber-50 text-amber-600",
    purple: "bg-purple-50 text-purple-600",
  };
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm text-gray-500">{title}</p>
        <span className={`w-9 h-9 rounded-lg flex items-center justify-center text-lg ${colorMap[color as keyof typeof colorMap]}`}>
          {icon}
        </span>
      </div>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
    </div>
  );
}

function CostRow({ label, amount, currency, bold }: { label: string; amount: number; currency: string; bold?: boolean }) {
  return (
    <div className={`flex justify-between items-center ${bold ? "font-semibold" : ""}`}>
      <span className="text-sm text-gray-600">{label}</span>
      <span className={`text-sm ${bold ? "text-gray-900" : "text-gray-700"}`}>
        {currency}{amount.toFixed(2)}
      </span>
    </div>
  );
}
