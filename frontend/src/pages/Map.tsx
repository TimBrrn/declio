import { Link } from '@tanstack/react-router'
import { useAuth } from '../auth/AuthProvider'
import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// ── Decorative pin data with real GPS coordinates ────────────────────────────

interface MapPin {
  city: string
  region: string
  lat: number
  lng: number
  count: number
}

const PINS: MapPin[] = [
  { city: 'Paris', region: 'Ile-de-France', lat: 48.8566, lng: 2.3522, count: 12 },
  { city: 'Lyon', region: 'Auvergne-Rhone-Alpes', lat: 45.764, lng: 4.8357, count: 8 },
  { city: 'Marseille', region: 'Provence-Alpes-Cote d\'Azur', lat: 43.2965, lng: 5.3698, count: 6 },
  { city: 'Toulouse', region: 'Occitanie', lat: 43.6047, lng: 1.4442, count: 5 },
  { city: 'Bordeaux', region: 'Nouvelle-Aquitaine', lat: 44.8378, lng: -0.5792, count: 4 },
  { city: 'Nantes', region: 'Pays de la Loire', lat: 47.2184, lng: -1.5536, count: 4 },
  { city: 'Lille', region: 'Hauts-de-France', lat: 50.6292, lng: 3.0573, count: 3 },
  { city: 'Strasbourg', region: 'Grand Est', lat: 48.5734, lng: 7.7521, count: 3 },
  { city: 'Rennes', region: 'Bretagne', lat: 48.1173, lng: -1.6778, count: 3 },
  { city: 'Nice', region: 'Provence-Alpes-Cote d\'Azur', lat: 43.7102, lng: 7.262, count: 2 },
  { city: 'Montpellier', region: 'Occitanie', lat: 43.6108, lng: 3.8767, count: 2 },
  { city: 'Grenoble', region: 'Auvergne-Rhone-Alpes', lat: 45.1885, lng: 5.7245, count: 2 },
  { city: 'Dijon', region: 'Bourgogne-Franche-Comte', lat: 47.322, lng: 5.0415, count: 2 },
  { city: 'Clermont-Ferrand', region: 'Auvergne-Rhone-Alpes', lat: 45.7772, lng: 3.087, count: 2 },
  { city: 'Tours', region: 'Centre-Val de Loire', lat: 47.3941, lng: 0.6848, count: 1 },
  { city: 'Angers', region: 'Pays de la Loire', lat: 47.4784, lng: -0.5632, count: 1 },
  { city: 'Brest', region: 'Bretagne', lat: 48.3904, lng: -4.4861, count: 1 },
  { city: 'Perpignan', region: 'Occitanie', lat: 42.6887, lng: 2.8948, count: 1 },
  { city: 'Metz', region: 'Grand Est', lat: 49.1193, lng: 6.1757, count: 1 },
  { city: 'Limoges', region: 'Nouvelle-Aquitaine', lat: 45.8336, lng: 1.2611, count: 1 },
]

const TOTAL_PRACTITIONERS = PINS.reduce((sum, p) => sum + p.count, 0)

// ── Leaflet Map component ────────────────────────────────────────────────────

function FranceMap() {
  const mapRef = useRef<HTMLDivElement>(null)
  const leafletMap = useRef<L.Map | null>(null)

  useEffect(() => {
    if (!mapRef.current || leafletMap.current) return

    const map = L.map(mapRef.current, {
      center: [46.6, 2.5],
      zoom: 6,
      zoomControl: false,
      attributionControl: false,
      scrollWheelZoom: false,
      dragging: true,
      doubleClickZoom: false,
    })

    // Light tile layer (CartoDB Positron)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
      subdomains: 'abcd',
      maxZoom: 10,
      minZoom: 5,
    }).addTo(map)

    L.control.zoom({ position: 'topright' }).addTo(map)

    // Markers
    PINS.forEach((pin) => {
      const size = Math.min(16 + pin.count * 3, 40)

      const icon = L.divIcon({
        className: 'declio-marker',
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2],
        html: `
          <div style="
            width: ${size}px;
            height: ${size}px;
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
          ">
            <div style="
              position: absolute;
              inset: 0;
              border-radius: 50%;
              background: rgba(13, 148, 136, 0.12);
            "></div>
            <div style="
              width: ${size * 0.6}px;
              height: ${size * 0.6}px;
              border-radius: 50%;
              background: rgba(13, 148, 136, 0.85);
              border: 2px solid rgba(13, 148, 136, 0.2);
              box-shadow: 0 0 ${size * 0.5}px rgba(13, 148, 136, 0.25);
            "></div>
          </div>
        `,
      })

      L.marker([pin.lat, pin.lng], { icon })
        .bindPopup(`
          <div style="
            background: white;
            color: #1c1917;
            padding: 12px 16px;
            border-radius: 12px;
            border: 1px solid #e7e5e4;
            font-family: system-ui, -apple-system, sans-serif;
            min-width: 140px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
          ">
            <div style="font-weight: 600; font-size: 14px; margin-bottom: 2px; color: #1c1917;">${pin.city}</div>
            <div style="color: #78716c; font-size: 12px; margin-bottom: 6px;">${pin.region}</div>
            <div style="color: #0d9488; font-size: 12px; font-weight: 500;">${pin.count} praticien${pin.count > 1 ? 's' : ''}</div>
          </div>
        `, {
          className: 'declio-popup',
          closeButton: false,
          offset: [0, -size / 2],
        })
        .addTo(map)
    })

    leafletMap.current = map

    return () => {
      map.remove()
      leafletMap.current = null
    }
  }, [])

  return (
    <div
      ref={mapRef}
      className="w-full rounded-2xl overflow-hidden border border-stone-200/60"
      style={{ height: '550px' }}
    />
  )
}

// ── Page component ───────────────────────────────────────────────────────────

export function MapPage() {
  const { isAuthenticated } = useAuth()

  return (
    <div className="min-h-screen bg-stone-50 text-stone-800 overflow-hidden">
      {/* Leaflet popup + marker overrides */}
      <style>{`
        .declio-marker {
          background: none !important;
          border: none !important;
        }
        .declio-popup .leaflet-popup-content-wrapper {
          background: transparent !important;
          box-shadow: none !important;
          border-radius: 0 !important;
          padding: 0 !important;
        }
        .declio-popup .leaflet-popup-content {
          margin: 0 !important;
        }
        .declio-popup .leaflet-popup-tip {
          background: white !important;
          border: 1px solid #e7e5e4 !important;
          box-shadow: none !important;
        }
        .leaflet-control-zoom a {
          background: white !important;
          color: #78716c !important;
          border-color: #e7e5e4 !important;
        }
        .leaflet-control-zoom a:hover {
          background: #fafaf9 !important;
          color: #1c1917 !important;
        }
      `}</style>

      {/* ── Nav ─────────────────────────────────────────────────────────────── */}
      <nav className="fixed top-0 inset-x-0 z-50 bg-white/80 backdrop-blur-lg border-b border-stone-200/60">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5 no-underline">
            <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
              </svg>
            </div>
            <span className="text-lg font-semibold text-stone-900">Declio</span>
          </Link>

          <div className="flex items-center gap-1">
            <Link
              to="/"
              className="px-4 py-2 text-sm font-medium text-stone-500 hover:text-stone-800 transition-colors no-underline"
            >
              Accueil
            </Link>
            <Link
              to="/map"
              className="px-4 py-2 text-sm font-medium text-stone-900 no-underline"
            >
              Carte
            </Link>
            <div className="w-px h-5 bg-stone-200 mx-2" />
            {isAuthenticated ? (
              <Link
                to="/dashboard"
                className="px-5 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 transition-colors no-underline"
              >
                Tableau de bord
              </Link>
            ) : (
              <>
                <Link
                  to="/login"
                  className="hidden sm:inline-block px-4 py-2 text-sm font-medium text-stone-500 hover:text-stone-800 transition-colors no-underline"
                >
                  Connexion
                </Link>
                <Link
                  to="/login"
                  className="px-5 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 transition-colors no-underline"
                >
                  Essai gratuit
                </Link>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <section className="relative pt-32 pb-8 px-6">
        <div className="max-w-4xl mx-auto text-center relative z-10">
          <p className="text-primary-600 text-sm font-semibold uppercase tracking-widest mb-4">Notre reseau</p>
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-stone-900">
            <span className="text-primary-600">{TOTAL_PRACTITIONERS} praticiens</span>
            {' '}nous font confiance
          </h1>
          <p className="mt-6 text-lg text-stone-500 max-w-xl mx-auto leading-relaxed">
            Des kinesitherapeutes partout en France utilisent Declio pour ne plus manquer un seul appel.
          </p>
        </div>
      </section>

      {/* ── Map ────────────────────────────────────────────────────────────── */}
      <section className="px-6 pb-20">
        <div className="max-w-5xl mx-auto">
          <FranceMap />
        </div>
      </section>

      {/* ── Stats strip ────────────────────────────────────────────────────── */}
      <section className="pb-28 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard value={`${TOTAL_PRACTITIONERS}`} label="Praticiens" />
            <StatCard value="15" label="Villes" />
            <StatCard value="10" label="Regions" />
            <StatCard value="24/7" label="Disponibilite" />
          </div>
        </div>
      </section>

      {/* ── CTA ────────────────────────────────────────────────────────────── */}
      <section className="pb-28 px-6">
        <div className="max-w-2xl mx-auto text-center bg-primary-50/50 rounded-2xl py-16 px-8">
          <h2 className="text-3xl sm:text-4xl font-bold text-stone-900 tracking-tight">
            Rejoignez le reseau
          </h2>
          <p className="mt-4 text-lg text-stone-500">
            Configurez votre assistant en 5 minutes et rejoignez les praticiens qui ne manquent plus aucun appel.
          </p>
          <Link
            to={isAuthenticated ? '/dashboard' : '/login'}
            className="mt-10 inline-block px-10 py-4 bg-primary-600 text-white text-base font-semibold rounded-xl hover:bg-primary-700 transition-colors shadow-sm no-underline"
          >
            Commencer l'essai gratuit
          </Link>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────────────────────────── */}
      <footer className="py-10 px-6 bg-white border-t border-stone-200/60">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 bg-primary-600 rounded-md flex items-center justify-center">
              <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
              </svg>
            </div>
            <span className="text-sm font-medium text-stone-500">Declio</span>
          </div>
          <p className="text-xs text-stone-400">
            &copy; {new Date().getFullYear()} Declio. Secretaire IA pour kinesitherapeutes.
          </p>
        </div>
      </footer>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({ value, label }: { value: string; label: string }) {
  return (
    <div className="bg-white border border-stone-200/60 rounded-2xl p-6 text-center">
      <p className="text-2xl font-bold text-stone-900">{value}</p>
      <p className="mt-1 text-xs text-stone-400 uppercase tracking-wider font-medium">{label}</p>
    </div>
  )
}
