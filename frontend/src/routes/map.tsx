import { createFileRoute } from '@tanstack/react-router'
import { MapPage } from '../pages/Map'

export const Route = createFileRoute('/map')({
  component: MapPage,
})
