import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900">
      {/* Navigation */}
      <nav className="max-w-7xl mx-auto px-6 py-5 flex items-center justify-between">
        <span className="text-white font-bold text-lg flex items-center gap-2">
          <span>⚡</span> AI Web Generator
        </span>
        <div className="flex items-center gap-6">
          <Link href="/pricing" className="text-slate-300 hover:text-white text-sm transition-colors">
            Cennik
          </Link>
          <Link
            href="/dashboard"
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-500 transition-colors"
          >
            Dashboard →
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-5xl mx-auto px-6 pt-20 pb-32 text-center">
        <div className="inline-flex items-center gap-2 bg-indigo-500/10 border border-indigo-500/20 rounded-full px-4 py-2 mb-8">
          <span className="text-indigo-400 text-sm font-medium">🇵🇱 Budowany dla polskiego rynku</span>
        </div>

        <h1 className="text-5xl md:text-7xl font-bold text-white leading-tight mb-6">
          Twoja firma{" "}
          <span className="bg-gradient-to-r from-indigo-400 to-teal-400 bg-clip-text text-transparent">
            zasługuje na stronę
          </span>
        </h1>

        <p className="text-xl text-slate-300 max-w-3xl mx-auto mb-10 leading-relaxed">
          Automatycznie generujemy profesjonalne strony internetowe dla polskich firm.
          Bez agencji, bez wysokich kosztów — gotowa strona w 48 godzin od{" "}
          <strong className="text-white">29 PLN miesięcznie</strong>.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            href="/pricing"
            className="px-8 py-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-semibold text-lg transition-transform hover:scale-105"
          >
            Sprawdź cennik
          </Link>
          <Link
            href="#jak-dziala"
            className="px-8 py-4 bg-white/5 hover:bg-white/10 text-white rounded-xl font-semibold text-lg border border-white/10 transition-colors"
          >
            Jak to działa?
          </Link>
        </div>
      </section>

      {/* Stats */}
      <section className="border-y border-white/10 py-12">
        <div className="max-w-5xl mx-auto px-6 grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          {[
            { value: "750 tys.", label: "firm bez strony w Polsce" },
            { value: "48h", label: "czas od odkrycia do demo" },
            { value: "~$0.01", label: "koszt generowania strony" },
            { value: "10%", label: "szacowana konwersja" },
          ].map(({ value, label }) => (
            <div key={label}>
              <p className="text-3xl font-bold text-white mb-1">{value}</p>
              <p className="text-slate-400 text-sm">{label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="jak-dziala" className="max-w-5xl mx-auto px-6 py-24">
        <h2 className="text-3xl font-bold text-white text-center mb-16">Jak to działa?</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {[
            {
              step: "01",
              title: "Odkrywamy Twoją firmę",
              desc: "Automatycznie skanujemy Google Maps i OpenStreetMap w poszukiwaniu firm bez profesjonalnej strony.",
              icon: "🔍",
            },
            {
              step: "02",
              title: "AI generuje stronę",
              desc: "6 wyspecjalizowanych agentów AI tworzy treści, wybiera design i buduje kompletną stronę w Twoim języku.",
              icon: "🤖",
            },
            {
              step: "03",
              title: "Otrzymujesz gotowe demo",
              desc: "Zanim zapłacisz złotówkę — widzisz gotową stronę swojej firmy. Podoba się? Subskrybuj.",
              icon: "🚀",
            },
          ].map(({ step, title, desc, icon }) => (
            <div key={step} className="bg-white/5 rounded-2xl p-8 border border-white/10">
              <div className="flex items-center gap-3 mb-4">
                <span className="text-3xl">{icon}</span>
                <span className="text-indigo-400 font-mono text-sm font-bold">{step}</span>
              </div>
              <h3 className="text-white font-semibold text-xl mb-3">{title}</h3>
              <p className="text-slate-400 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-3xl mx-auto px-6 py-16 text-center">
        <div className="bg-indigo-600/20 border border-indigo-500/30 rounded-3xl p-12">
          <h2 className="text-3xl font-bold text-white mb-4">
            Gotowy sprawdzić swoje demo?
          </h2>
          <p className="text-slate-300 mb-8">
            Jeśli Twoja firma pojawiła się w naszym systemie, mamy już gotowe demo — za darmo.
          </p>
          <Link
            href="mailto:demo@yourplatform.pl"
            className="inline-block px-8 py-4 bg-white text-indigo-900 rounded-xl font-bold text-lg hover:bg-slate-100 transition-colors"
          >
            Poproś o swoje demo
          </Link>
        </div>
      </section>

      <footer className="max-w-7xl mx-auto px-6 py-8 border-t border-white/10 flex justify-between text-slate-500 text-sm">
        <p>&copy; {new Date().getFullYear()} AI Web Generator. Wszystkie prawa zastrzeżone.</p>
        <div className="flex gap-6">
          <Link href="/privacy" className="hover:text-slate-300">Prywatność</Link>
          <Link href="/terms" className="hover:text-slate-300">Regulamin</Link>
        </div>
      </footer>
    </main>
  );
}
