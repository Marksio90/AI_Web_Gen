import { PLANS } from "@/lib/stripe";

export const metadata = {
  title: "Cennik — AI Web Generator",
  description: "Profesjonalna strona internetowa dla Twojej firmy od 29 PLN miesięcznie.",
};

export default function PricingPage() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-800 py-20 px-4">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-16">
          <h1 className="text-4xl md:text-5xl font-bold text-white mb-4">
            Prosta, uczciwa cena
          </h1>
          <p className="text-slate-300 text-lg max-w-2xl mx-auto">
            Zamiast płacić 5,000–15,000 zł za stronę agencji — subskrybuj za ułamek tej kwoty.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-16">
          {Object.entries(PLANS).map(([key, plan], i) => (
            <div
              key={key}
              className={`relative rounded-2xl p-8 ${
                i === 1
                  ? "bg-indigo-600 text-white ring-4 ring-indigo-400"
                  : "bg-white/5 text-white border border-white/10"
              }`}
            >
              {i === 1 && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-amber-400 text-amber-900 text-xs font-bold px-4 py-1 rounded-full">
                  NAJPOPULARNIEJSZY
                </div>
              )}
              <h2 className="text-xl font-bold mb-2">{plan.name}</h2>
              <div className="flex items-baseline gap-1 mb-6">
                <span className="text-4xl font-bold">{plan.price}</span>
                <span className="text-sm opacity-70">PLN/mies.</span>
              </div>
              <ul className="space-y-3 mb-8">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-2 text-sm">
                    <span className="text-green-400 mt-0.5 flex-shrink-0">✓</span>
                    {feature}
                  </li>
                ))}
              </ul>
              <a
                href={`/checkout?plan=${key}`}
                className={`block text-center py-3 px-6 rounded-xl font-semibold transition-transform hover:scale-105 ${
                  i === 1
                    ? "bg-white text-indigo-600"
                    : "bg-indigo-600 text-white hover:bg-indigo-500"
                }`}
              >
                Wybierz {plan.name}
              </a>
            </div>
          ))}
        </div>

        {/* Comparison with traditional agencies */}
        <div className="bg-white/5 rounded-2xl p-8 border border-white/10">
          <h2 className="text-2xl font-bold text-white mb-6 text-center">
            Dlaczego nie agencja?
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
            <ComparisonCard
              label="Freelancer"
              price="2,000–5,000 zł"
              time="2–6 tygodni"
              icon="👤"
              bad
            />
            <ComparisonCard
              label="Agencja"
              price="5,000–15,000 zł"
              time="4–12 tygodni"
              icon="🏢"
              bad
            />
            <ComparisonCard
              label="AI Web Generator"
              price="od 29 zł/mies."
              time="48 godzin"
              icon="⚡"
              good
            />
          </div>
        </div>

        <p className="text-center text-slate-400 text-sm mt-8">
          Akceptujemy: Karta bankowa · BLIK · Przelewy24 · PayPal
        </p>
      </div>
    </main>
  );
}

function ComparisonCard({
  label, price, time, icon, bad, good,
}: {
  label: string; price: string; time: string; icon: string; bad?: boolean; good?: boolean;
}) {
  return (
    <div className={`rounded-xl p-6 ${good ? "bg-indigo-600/20 border border-indigo-400" : "bg-white/5"}`}>
      <p className="text-3xl mb-3">{icon}</p>
      <p className="text-white font-semibold mb-2">{label}</p>
      <p className={`text-lg font-bold mb-1 ${bad ? "text-red-400" : "text-green-400"}`}>{price}</p>
      <p className="text-slate-400 text-sm">{time}</p>
    </div>
  );
}
