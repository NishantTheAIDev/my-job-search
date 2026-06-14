import { api } from './client'
import type { Insights, SalaryStat, InsightsRegion } from '../types'

export async function getInsights(region: InsightsRegion): Promise<Insights> {
  const p = new URLSearchParams()
  p.set('region', region)
  const response = await api.get<Insights>(`/insights?${p.toString()}`)
  return response.data
}

export async function getSalary(role: string, region: InsightsRegion): Promise<SalaryStat> {
  const p = new URLSearchParams()
  p.set('role', role)
  p.set('region', region)
  const response = await api.get<SalaryStat>(`/insights/salary?${p.toString()}`)
  return response.data
}
