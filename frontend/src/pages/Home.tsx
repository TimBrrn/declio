import { Link } from '@tanstack/react-router'
import { useAuth } from '../auth/AuthProvider'

export function Home() {
  const { isAuthenticated } = useAuth()
  const ctaTo = isAuthenticated ? '/dashboard' : '/login'

  return (
    <div className="min-h-screen bg-stone-950 text-white overflow-hidden">
      {/* ── Nav ─────────────────────────────────────────────────────────────── */}
      <nav className="fixed top-0 inset-x-0 z-50 bg-stone-950/70 backdrop-blur-xl border-b border-white/5">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5 no-underline">
            <div className="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
              </svg>
            </div>
            <span className="text-lg font-semibold text-white">Declio</span>
          </Link>

          <div className="flex items-center gap-3">
            {isAuthenticated ? (
              <Link
                to="/dashboard"
                className="px-5 py-2 bg-white text-stone-900 text-sm font-medium rounded-lg hover:bg-stone-100 transition-colors no-underline"
              >
                Tableau de bord
              </Link>
            ) : (
              <>
                <Link
                  to="/login"
                  className="hidden sm:inline-block px-4 py-2 text-sm font-medium text-stone-300 hover:text-white transition-colors no-underline"
                >
                  Connexion
                </Link>
                <Link
                  to="/login"
                  className="px-5 py-2 bg-primary-500 text-white text-sm font-medium rounded-lg hover:bg-primary-400 transition-colors no-underline"
                >
                  Essai gratuit
                </Link>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* ── Hero ────────────────────────────────────────────────────────────── */}
      <section className="relative pt-40 pb-28 px-6">
        {/* Glow effects */}
        <div className="absolute top-20 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-primary-500/15 rounded-full blur-[128px] pointer-events-none" />
        <div className="absolute top-40 left-1/4 w-[300px] h-[300px] bg-primary-400/10 rounded-full blur-[96px] pointer-events-none" />

        <div className="max-w-4xl mx-auto text-center relative z-10">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/5 backdrop-blur-sm border border-white/10 text-primary-300 text-xs font-semibold rounded-full mb-8 tracking-wide uppercase">
            <span className="w-1.5 h-1.5 rounded-full bg-primary-400 animate-pulse" />
            Secretaire IA pour kinesitherapeutes
          </div>

          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.05]">
            <span className="text-white">Ne manquez plus</span>
            <br />
            <span className="bg-gradient-to-r from-primary-300 via-primary-400 to-primary-500 bg-clip-text text-transparent">aucun appel.</span>
          </h1>

          <p className="mt-8 text-lg sm:text-xl text-stone-400 max-w-2xl mx-auto leading-relaxed">
            Declio repond a vos patients 24h/24, gere les rendez-vous,
            et vous envoie un resume par SMS apres chaque appel.
          </p>

          <div className="mt-12 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              to={ctaTo}
              className="w-full sm:w-auto px-8 py-4 bg-primary-500 text-white text-base font-semibold rounded-xl hover:bg-primary-400 transition-all shadow-lg shadow-primary-500/25 hover:shadow-xl hover:shadow-primary-500/30 no-underline"
            >
              Demarrer gratuitement
            </Link>
            <a
              href="#fonctionnement"
              className="w-full sm:w-auto px-8 py-4 bg-white/5 backdrop-blur-sm text-stone-300 text-base font-medium rounded-xl border border-white/10 hover:bg-white/10 hover:text-white transition-all no-underline text-center"
            >
              Decouvrir
            </a>
          </div>

          {/* Metrics strip */}
          <div className="mt-20 flex flex-wrap items-center justify-center gap-8 sm:gap-16">
            <MetricPill value="< 2s" label="Temps de reponse" />
            <MetricPill value="24/7" label="Disponibilite" />
            <MetricPill value="100%" label="Appels traites" />
          </div>
        </div>
      </section>

      {/* ── How it works ────────────────────────────────────────────────────── */}
      <section id="fonctionnement" className="py-28 px-6 relative">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-primary-500/[0.03] to-transparent pointer-events-none" />
        <div className="max-w-5xl mx-auto relative z-10">
          <div className="text-center mb-20">
            <p className="text-primary-400 text-sm font-semibold uppercase tracking-widest mb-4">Fonctionnement</p>
            <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
              Simple comme un appel
            </h2>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            <StepCard
              step="01"
              title="Le patient appelle"
              description="Declio decroche instantanement avec un message d'accueil personnalise a votre cabinet."
              icon={
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z" />
                </svg>
              }
            />
            <StepCard
              step="02"
              title="L'IA traite la demande"
              description="Prise de rendez-vous, annulation, questions sur les tarifs ou horaires — tout est gere."
              icon={
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
                </svg>
              }
            />
            <StepCard
              step="03"
              title="Vous recevez un SMS"
              description="Un resume de l'appel avec les actions effectuees, directement sur votre telephone."
              icon={
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
                </svg>
              }
            />
          </div>
        </div>
      </section>

      {/* ── Features ────────────────────────────────────────────────────────── */}
      <section className="py-28 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-20">
            <p className="text-primary-400 text-sm font-semibold uppercase tracking-widest mb-4">Fonctionnalites</p>
            <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
              Concu pour les kinesitherapeutes
            </h2>
            <p className="mt-4 text-lg text-stone-400 max-w-xl mx-auto">
              Tout ce dont votre cabinet a besoin, rien de superflu.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 gap-5">
            <FeatureCard
              title="Prise de rendez-vous"
              description="L'IA consulte vos disponibilites, propose des creneaux et confirme la reservation dans votre agenda Google."
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
                </svg>
              }
            />
            <FeatureCard
              title="Annulation et report"
              description="Le patient peut annuler ou reporter son rendez-vous. L'agenda est mis a jour automatiquement."
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
                </svg>
              }
            />
            <FeatureCard
              title="FAQ automatique"
              description="Tarifs, horaires, adresse, documents a apporter — l'assistant repond a toutes les questions courantes."
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z" />
                </svg>
              }
            />
            <FeatureCard
              title="Tableau de bord"
              description="Historique des appels, couts, scenarios traites et performance — tout en temps reel."
              icon={
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
                </svg>
              }
            />
          </div>
        </div>
      </section>

      {/* ── CTA ─────────────────────────────────────────────────────────────── */}
      <section className="py-28 px-6 relative">
        <div className="absolute inset-0 bg-gradient-to-t from-primary-500/[0.06] to-transparent pointer-events-none" />
        <div className="max-w-2xl mx-auto text-center relative z-10">
          <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
            Pret a ne plus manquer d'appels ?
          </h2>
          <p className="mt-4 text-lg text-stone-400">
            Configurez votre assistant en 5 minutes. Aucune carte bancaire requise.
          </p>
          <Link
            to={ctaTo}
            className="mt-10 inline-block px-10 py-4 bg-primary-500 text-white text-base font-semibold rounded-xl hover:bg-primary-400 transition-all shadow-lg shadow-primary-500/25 hover:shadow-xl hover:shadow-primary-500/30 no-underline"
          >
            Commencer l'essai gratuit
          </Link>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────────────────────────── */}
      <footer className="py-10 px-6 border-t border-white/5">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 bg-primary-500 rounded-md flex items-center justify-center">
              <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
              </svg>
            </div>
            <span className="text-sm font-medium text-stone-400">Declio</span>
          </div>
          <p className="text-xs text-stone-600">
            &copy; {new Date().getFullYear()} Declio. Secretaire IA pour kinesitherapeutes.
          </p>
        </div>
      </footer>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

function MetricPill({ value, label }: { value: string; label: string }) {
  return (
    <div className="text-center">
      <p className="text-2xl sm:text-3xl font-bold text-white">{value}</p>
      <p className="mt-1 text-xs text-stone-500 uppercase tracking-wider font-medium">{label}</p>
    </div>
  )
}

function StepCard({
  step,
  title,
  description,
  icon,
}: {
  step: string
  title: string
  description: string
  icon: React.ReactNode
}) {
  return (
    <div className="group relative bg-white/[0.03] backdrop-blur-sm border border-white/[0.06] rounded-2xl p-8 hover:bg-white/[0.05] hover:border-white/10 transition-all">
      <div className="flex items-center justify-between mb-6">
        <div className="w-12 h-12 bg-primary-500/10 rounded-xl flex items-center justify-center text-primary-400">
          {icon}
        </div>
        <span className="text-xs font-mono text-stone-600 tracking-wider">{step}</span>
      </div>
      <h3 className="text-lg font-semibold text-white">{title}</h3>
      <p className="mt-3 text-sm text-stone-400 leading-relaxed">{description}</p>
    </div>
  )
}

function FeatureCard({
  title,
  description,
  icon,
}: {
  title: string
  description: string
  icon: React.ReactNode
}) {
  return (
    <div className="group bg-white/[0.03] backdrop-blur-sm border border-white/[0.06] rounded-2xl p-7 hover:bg-white/[0.05] hover:border-white/10 transition-all">
      <div className="w-10 h-10 bg-primary-500/10 rounded-xl flex items-center justify-center text-primary-400 mb-5 group-hover:bg-primary-500/15 transition-colors">
        {icon}
      </div>
      <h3 className="text-base font-semibold text-white">{title}</h3>
      <p className="mt-2 text-sm text-stone-400 leading-relaxed">{description}</p>
    </div>
  )
}
