import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import {
  getCabinets,
  createCabinet,
  updateCabinet,
  type CabinetCreate,
  type WeekSchedule,
  type PaymentMode,
} from "../api/client";

const DAYS = [
  "lundi",
  "mardi",
  "mercredi",
  "jeudi",
  "vendredi",
  "samedi",
  "dimanche",
] as const;

const DEFAULT_SCHEDULE: WeekSchedule = {
  lundi: { open: "09:00", close: "19:00", closed: false },
  mardi: { open: "09:00", close: "19:00", closed: false },
  mercredi: { open: "09:00", close: "19:00", closed: false },
  jeudi: { open: "09:00", close: "19:00", closed: false },
  vendredi: { open: "09:00", close: "19:00", closed: false },
  samedi: { open: "09:00", close: "13:00", closed: false },
  dimanche: { open: "09:00", close: "12:00", closed: true },
};

const EMPTY_FORM: CabinetCreate = {
  nom_cabinet: "",
  nom_praticien: "",
  adresse: "",
  telephone: "",
  horaires: DEFAULT_SCHEDULE,
  tarifs: {
    seance_conventionnelle: 0,
    depassement: 0,
    modes_paiement: ["cb", "especes"],
  },
  google_calendar_id: "",
  numero_sms_kine: "",
  message_accueil: "",
  faq: {},
};

const PAYMENT_OPTIONS: { value: PaymentMode; label: string }[] = [
  { value: "cb", label: "Carte bancaire" },
  { value: "cheque", label: "Cheque" },
  { value: "especes", label: "Especes" },
];

const FR_PHONE = /^(?:(?:\+33|0033|0)[1-9])(?:\d{8})$/;

function stripSpaces(v: string) {
  return v.replace(/\s/g, "");
}

type Tab = "general" | "horaires" | "integrations";

const FIELD_TO_TAB: Record<string, Tab> = {
  nom_cabinet: "general",
  nom_praticien: "general",
  adresse: "general",
  telephone: "general",
  message_accueil: "general",
  numero_sms_kine: "integrations",
  google_calendar_id: "integrations",
};

export function CabinetConfig() {
  const queryClient = useQueryClient();
  const {
    data: cabinets,
    isLoading: loadingCabinets,
    isError: queryError,
  } = useQuery({
    queryKey: ["cabinets"],
    queryFn: getCabinets,
    retry: false,
  });

  const existing = cabinets?.[0] ?? null;
  const noCabinetYet = cabinets && cabinets.length === 0;
  const [form, setForm] = useState<CabinetCreate>(EMPTY_FORM);
  const [initialized, setInitialized] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [activeTab, setActiveTab] = useState<Tab>("general");
  const [toast, setToast] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  // Sync form when existing data loads
  useEffect(() => {
    if (existing && !initialized) {
      const { id: _, ...rest } = existing;
      setForm({
        ...EMPTY_FORM,
        ...rest,
        tarifs: { ...EMPTY_FORM.tarifs, ...rest.tarifs },
        horaires: { ...EMPTY_FORM.horaires, ...rest.horaires },
      });
      setInitialized(true);
      setShowForm(true);
    }
  }, [existing, initialized]);

  const mutation = useMutation({
    mutationFn: (data: CabinetCreate) =>
      existing ? updateCabinet(existing.id, data) : createCabinet(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cabinets"] });
      showToast(
        "success",
        existing ? "Configuration mise a jour" : "Cabinet cree avec succes",
      );
    },
    onError: (err: Error) => {
      showToast("error", `Erreur : ${err.message}`);
    },
  });

  function showToast(type: "success" | "error", message: string) {
    setToast({ type, message });
    setTimeout(() => setToast(null), 4000);
  }

  function tabsWithErrors(errs: Record<string, string>): Set<Tab> {
    const tabs = new Set<Tab>();
    for (const field of Object.keys(errs)) {
      const tab = FIELD_TO_TAB[field];
      if (tab) tabs.add(tab);
    }
    return tabs;
  }

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!form.nom_cabinet.trim()) e.nom_cabinet = "Champ requis";
    if (!form.nom_praticien.trim()) e.nom_praticien = "Champ requis";
    if (!form.adresse.trim()) e.adresse = "Champ requis";
    if (!FR_PHONE.test(stripSpaces(form.telephone)))
      e.telephone = "Numero invalide (ex: 06 12 34 56 78 ou +33612345678)";
    if (
      form.numero_sms_kine &&
      !FR_PHONE.test(stripSpaces(form.numero_sms_kine))
    )
      e.numero_sms_kine =
        "Numero invalide (ex: 06 12 34 56 78 ou +33612345678)";
    setErrors(e);
    if (Object.keys(e).length > 0) {
      const errorTabs = tabsWithErrors(e);
      const tabOrder: Tab[] = ["general", "horaires", "integrations"];
      const firstErrorTab = tabOrder.find((t) => errorTabs.has(t));
      if (firstErrorTab) setActiveTab(firstErrorTab);
      return false;
    }
    return true;
  }

  const errorTabSet = tabsWithErrors(errors);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    mutation.mutate(form);
  }

  function set<K extends keyof CabinetCreate>(key: K, value: CabinetCreate[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }

  function togglePayment(mode: PaymentMode) {
    const current = form.tarifs.modes_paiement;
    const next = current.includes(mode)
      ? current.filter((m) => m !== mode)
      : [...current, mode];
    set("tarifs", { ...form.tarifs, modes_paiement: next });
  }

  if (loadingCabinets) {
    return <LoadingSkeleton />;
  }

  // Onboarding screen when no cabinet configured
  if (noCabinetYet && !showForm && !queryError) {
    return <OnboardingScreen onStart={() => setShowForm(true)} />;
  }

  return (
    <div className="max-w-3xl relative">
      {/* Toast */}
      {toast && (
        <Toast
          type={toast.type}
          message={toast.message}
          onClose={() => setToast(null)}
        />
      )}

      {queryError && (
        <div className="mb-6 p-4 bg-amber-50 rounded-xl">
          <p className="text-sm text-amber-800">
            Impossible de joindre le serveur. Vous pouvez remplir le formulaire
            — il sera envoye des que le backend sera disponible.
          </p>
        </div>
      )}

      <h1 className="text-2xl font-semibold text-stone-900">
        Configuration du cabinet
      </h1>
      <p className="mt-1 text-sm text-stone-500">
        {existing
          ? "Modifiez les informations de votre cabinet."
          : "Renseignez les informations de votre cabinet pour demarrer."}
      </p>

      <form onSubmit={handleSubmit} className="mt-8">
        {/* Tab bar */}
        <TabBar
          activeTab={activeTab}
          onTabChange={setActiveTab}
          errorTabs={errorTabSet}
        />

        {/* Tab: General */}
        <div className={activeTab === "general" ? "space-y-6 mt-6" : "hidden"}>
          <Section title="Informations generales">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Nom du cabinet" required error={errors.nom_cabinet}>
                <input
                  type="text"
                  value={form.nom_cabinet}
                  onChange={(e) => set("nom_cabinet", e.target.value)}
                  placeholder="Cabinet Dupont Kine"
                  className={inputClass(errors.nom_cabinet)}
                />
              </Field>
              <Field
                label="Nom du praticien"
                required
                error={errors.nom_praticien}
              >
                <input
                  type="text"
                  value={form.nom_praticien}
                  onChange={(e) => set("nom_praticien", e.target.value)}
                  placeholder="Marie Dupont"
                  className={inputClass(errors.nom_praticien)}
                />
              </Field>
            </div>
            <Field label="Adresse" required error={errors.adresse}>
              <input
                type="text"
                value={form.adresse}
                onChange={(e) => set("adresse", e.target.value)}
                placeholder="12 rue de la Sante, 75013 Paris"
                className={inputClass(errors.adresse)}
              />
            </Field>
            <Field
              label="Telephone du cabinet"
              required
              error={errors.telephone}
            >
              <input
                type="tel"
                value={form.telephone}
                onChange={(e) => set("telephone", e.target.value)}
                placeholder="01 23 45 67 89"
                className={inputClass(errors.telephone)}
              />
            </Field>
          </Section>

          <Section title="Message d'accueil">
            <Field
              label="Message d'accueil"
              hint="Ce message sera lu par l'assistant en debut d'appel"
            >
              <textarea
                value={form.message_accueil}
                onChange={(e) => set("message_accueil", e.target.value)}
                rows={3}
                placeholder="Bonjour, vous etes bien au cabinet de kinesitherapie Dupont. Je suis l'assistant virtuel du cabinet. Comment puis-je vous aider ?"
                className={inputClass()}
              />
            </Field>
          </Section>
        </div>

        {/* Tab: Horaires & Tarifs */}
        <div className={activeTab === "horaires" ? "space-y-6 mt-6" : "hidden"}>
          <Section title="Horaires d'ouverture">
            <div className="space-y-3">
              {DAYS.map((day) => (
                <ScheduleRow
                  key={day}
                  day={day}
                  value={form.horaires[day]}
                  onChange={(val) =>
                    set("horaires", { ...form.horaires, [day]: val })
                  }
                />
              ))}
            </div>
          </Section>

          <Section title="Tarifs">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Seance conventionnelle">
                <div className="relative">
                  <input
                    type="number"
                    min={0}
                    step={0.01}
                    value={form.tarifs.seance_conventionnelle || ""}
                    onChange={(e) =>
                      set("tarifs", {
                        ...form.tarifs,
                        seance_conventionnelle: +e.target.value,
                      })
                    }
                    placeholder="16.13"
                    className={inputClass()}
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-stone-400 text-sm">
                    EUR
                  </span>
                </div>
              </Field>
              <Field label="Depassement">
                <div className="relative">
                  <input
                    type="number"
                    min={0}
                    step={0.01}
                    value={form.tarifs.depassement || ""}
                    onChange={(e) =>
                      set("tarifs", {
                        ...form.tarifs,
                        depassement: +e.target.value,
                      })
                    }
                    placeholder="10.00"
                    className={inputClass()}
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-stone-400 text-sm">
                    EUR
                  </span>
                </div>
              </Field>
            </div>
            <Field label="Modes de paiement acceptes">
              <div className="flex flex-wrap gap-4 mt-1">
                {PAYMENT_OPTIONS.map((opt) => (
                  <label
                    key={opt.value}
                    className="flex items-center gap-2 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={form.tarifs.modes_paiement.includes(opt.value)}
                      onChange={() => togglePayment(opt.value)}
                      className="rounded border-stone-300 text-primary-600 focus:ring-primary-500"
                    />
                    <span className="text-sm text-stone-700">{opt.label}</span>
                  </label>
                ))}
              </div>
            </Field>
          </Section>
        </div>

        {/* Tab: Integrations */}
        <div
          className={activeTab === "integrations" ? "space-y-6 mt-6" : "hidden"}
        >
          <Section title="Integrations">
            <Field
              label="Google Calendar ID"
              hint="Trouvez-le dans Parametres Google Calendar > Integrer l'agenda > ID de l'agenda"
            >
              <input
                type="text"
                value={form.google_calendar_id}
                onChange={(e) => set("google_calendar_id", e.target.value)}
                placeholder="exemple@group.calendar.google.com"
                className={inputClass()}
              />
            </Field>
            <Field
              label="Numero SMS du kine"
              error={errors.numero_sms_kine}
              hint="Numero sur lequel vous recevrez les resumes d'appels par SMS"
            >
              <input
                type="tel"
                value={form.numero_sms_kine}
                onChange={(e) => set("numero_sms_kine", e.target.value)}
                placeholder="+33 6 12 34 56 78"
                className={inputClass(errors.numero_sms_kine)}
              />
            </Field>
          </Section>
        </div>

        {/* Actions — always visible */}
        <div className="flex items-center gap-4 pt-8">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="inline-flex items-center gap-2 px-6 py-3 bg-primary-600 text-white text-sm font-medium rounded-xl hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
          >
            {mutation.isPending && <Spinner />}
            {mutation.isPending
              ? "Enregistrement..."
              : existing
                ? "Mettre a jour"
                : "Creer le cabinet"}
          </button>
        </div>
      </form>
    </div>
  );
}

// ── Sub-components ───────────────────────────────────────────────────────────

const TABS: { key: Tab; label: string }[] = [
  { key: "general", label: "General" },
  { key: "horaires", label: "Horaires & Tarifs" },
  { key: "integrations", label: "Integrations" },
];

function TabBar({
  activeTab,
  onTabChange,
  errorTabs,
}: {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
  errorTabs: Set<Tab>;
}) {
  return (
    <div className="flex gap-6 border-b border-stone-200">
      {TABS.map(({ key, label }) => (
        <button
          key={key}
          type="button"
          onClick={() => onTabChange(key)}
          className={`relative pb-3 text-sm font-medium transition-colors ${
            activeTab === key
              ? "text-primary-600 border-b-2 border-primary-600"
              : "text-stone-500 hover:text-stone-700"
          }`}
        >
          {label}
          {errorTabs.has(key) && (
            <span className="absolute -top-0.5 -right-2.5 w-2 h-2 bg-rose-500 rounded-full" />
          )}
        </button>
      ))}
    </div>
  );
}

function OnboardingScreen({ onStart }: { onStart: () => void }) {
  return (
    <div className="max-w-lg mx-auto text-center py-16">
      <div className="w-16 h-16 bg-primary-50 rounded-2xl flex items-center justify-center mx-auto">
        <svg
          className="w-8 h-8 text-primary-600"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"
          />
        </svg>
      </div>
      <h1 className="mt-6 text-2xl font-semibold text-stone-900">
        Bienvenue sur Declio !
      </h1>
      <p className="mt-3 text-stone-500">
        Commencez par configurer votre cabinet pour que l'assistant vocal puisse
        repondre a vos appels.
      </p>
      <button
        onClick={onStart}
        className="mt-8 px-6 py-3 bg-primary-600 text-white text-sm font-medium rounded-xl hover:bg-primary-700 transition-colors shadow-sm"
      >
        Configurer mon cabinet
      </button>
      <p className="mt-4 text-xs text-stone-400">
        Vous pourrez modifier ces informations a tout moment.
      </p>
    </div>
  );
}

function Toast({
  type,
  message,
  onClose,
}: {
  type: "success" | "error";
  message: string;
  onClose: () => void;
}) {
  const barColor = type === "success" ? "bg-primary-500" : "bg-rose-500";
  const iconColor = type === "success" ? "text-primary-600" : "text-rose-600";
  const icon =
    type === "success" ? (
      <svg
        className={`w-5 h-5 ${iconColor}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
      </svg>
    ) : (
      <svg
        className={`w-5 h-5 ${iconColor}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M6 18L18 6M6 6l12 12"
        />
      </svg>
    );

  return (
    <div className="fixed bottom-6 right-6 z-50 flex items-stretch bg-white rounded-xl shadow-lg overflow-hidden animate-slide-in-bottom">
      <div className={`w-1 ${barColor}`} />
      <div className="flex items-center gap-3 px-4 py-3">
        {icon}
        <span className="text-sm font-medium text-stone-800">{message}</span>
        <button
          onClick={onClose}
          className="ml-2 text-stone-400 hover:text-stone-600 transition-colors"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <fieldset className="bg-white rounded-xl shadow-sm p-6 space-y-4">
      <legend className="text-base font-semibold text-stone-900 -ml-2 px-2">
        {title}
      </legend>
      {children}
    </fieldset>
  );
}

function Field({
  label,
  required,
  error,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  error?: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-stone-700 mb-1">
        {label}
        {required && <span className="text-rose-500 ml-0.5">*</span>}
      </span>
      {hint && (
        <span className="block text-xs text-stone-400 mb-1.5">{hint}</span>
      )}
      {children}
      {error && (
        <span className="block text-sm text-rose-600 mt-1">{error}</span>
      )}
    </label>
  );
}

function ScheduleRow({
  day,
  value,
  onChange,
}: {
  day: string;
  value: { open: string; close: string; closed: boolean };
  onChange: (v: { open: string; close: string; closed: boolean }) => void;
}) {
  return (
    <div className="flex items-center gap-3 sm:gap-4">
      <span className="w-24 text-sm font-medium text-stone-700 capitalize">
        {day}
      </span>
      <label className="flex items-center gap-2 cursor-pointer min-w-20">
        <input
          type="checkbox"
          checked={!value.closed}
          onChange={(e) => onChange({ ...value, closed: !e.target.checked })}
          className="rounded border-stone-300 text-primary-600 focus:ring-primary-500"
        />
        <span
          className={`text-sm ${value.closed ? "text-stone-400" : "text-primary-700 font-medium"}`}
        >
          {value.closed ? "Ferme" : "Ouvert"}
        </span>
      </label>
      {!value.closed && (
        <div className="flex items-center gap-2">
          <input
            type="time"
            value={value.open}
            onChange={(e) => onChange({ ...value, open: e.target.value })}
            className="px-2 py-1.5 border border-stone-200 rounded-lg text-sm focus:ring-2 focus:ring-primary-500/20 focus:border-primary-600 outline-none transition-colors"
          />
          <span className="text-stone-400">-</span>
          <input
            type="time"
            value={value.close}
            onChange={(e) => onChange({ ...value, close: e.target.value })}
            className="px-2 py-1.5 border border-stone-200 rounded-lg text-sm focus:ring-2 focus:ring-primary-500/20 focus:border-primary-600 outline-none transition-colors"
          />
        </div>
      )}
    </div>
  );
}

function Spinner() {
  return (
    <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

function LoadingSkeleton() {
  return (
    <div className="max-w-3xl animate-pulse space-y-6">
      <div className="h-8 w-64 bg-stone-200 rounded" />
      <div className="h-4 w-48 bg-stone-200 rounded" />
      <div className="space-y-4">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-10 bg-stone-200 rounded-xl" />
        ))}
      </div>
    </div>
  );
}

function inputClass(error?: string) {
  return `block w-full px-3 py-3 border rounded-xl text-sm focus:ring-2 focus:ring-primary-500/20 focus:border-primary-600 outline-none transition-colors ${
    error ? "border-rose-300 bg-rose-50" : "border-stone-200 bg-white"
  }`;
}
