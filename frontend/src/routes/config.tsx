import { createFileRoute } from '@tanstack/react-router'
import { CabinetConfig } from '../pages/CabinetConfig'

export const Route = createFileRoute('/config')({
  component: CabinetConfig,
})
