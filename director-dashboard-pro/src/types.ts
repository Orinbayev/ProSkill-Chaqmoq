export interface MetricData {
  label: string;
  value: string | number;
  trend: number;
  status: 'success' | 'warning' | 'danger' | 'info';
  sparkline: { x: number; y: number }[];
}

export interface TeacherRanking {
  name: string;
  revenue: number;
  attendance: number;
  retention: number;
  image: string;
}

export interface RiskStudent {
  id: string;
  name: string;
  issue: string;
  riskLevel: number;
  debt: number;
  status: 'critical' | 'warning' | 'stable';
}

export interface GroupPerformance {
  name: string;
  revenue: number;
  debt: number;
  health: number;
  students: number;
}
