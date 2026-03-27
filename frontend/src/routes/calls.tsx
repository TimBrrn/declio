import { createFileRoute } from '@tanstack/react-router'
import { CallHistory } from '../pages/CallHistory'

export const Route = createFileRoute('/calls')({
  component: CallHistory,
})
