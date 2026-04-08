export type Period = 'bu_oy' | 'otgan_oy';

export interface DailyPoint {
  kun: string;
  daromad: number;
  xarajat: number;
  foyda: number;
  qarz: number;
}

export interface KPIData {
  daromad: number;
  foyda: number;
  marja: number;
  xarajat: number;
  qarz: number;
  faolOquvchi: number;
  konversiya: number;
  daromadDelta: number;
  foydaDelta: number;
  xarajatDelta: number;
  qarzDelta: number;
  faolOquvchiDelta: number;
  konversiyaDelta: number;
}

export interface PaymentData {
  completed: number;
  pending: number;
  overdue: number;
  total: number;
  ortachaTolov: number;
  tolovBajarildi: number;
  daromadSifati: number;
  qaytaTolov: number;
}

export interface TeacherRow {
  id: number;
  ism: string;
  guruhlar: number;
  oquvchilar: number;
  daromad: number;
  marja: number;
  baho: number;
}

export interface GroupRow {
  id: number;
  nom: string;
  ustoz: string;
  bolim: string;
  oquvchilar: number;
  daromad: number;
  status: 'aktiv' | 'toxtagan' | 'yangi';
}

export interface FunnelStage {
  nom: string;
  son: number;
  foiz: number;
  color: string;
}

export interface GoalItem {
  nom: string;
  maqsad: number;
  hozir: number;
  birlik: string;
}

export interface MockPeriodData {
  kpi: KPIData;
  daily: DailyPoint[];
  payment: PaymentData;
  teachers: TeacherRow[];
  groups: GroupRow[];
  funnel: FunnelStage[];
  goals: GoalItem[];
}

/* ─── BU OY ─────────────────────────────────────────────────────────────────── */
const buOyDaily: DailyPoint[] = [
  { kun: '01', daromad: 98_000_000,  xarajat: 32_000_000, foyda: 66_000_000,  qarz: 14_000_000 },
  { kun: '02', daromad: 121_000_000, xarajat: 28_500_000, foyda: 92_500_000,  qarz: 12_800_000 },
  { kun: '03', daromad: 87_000_000,  xarajat: 31_000_000, foyda: 56_000_000,  qarz: 13_200_000 },
  { kun: '04', daromad: 145_000_000, xarajat: 29_000_000, foyda: 116_000_000, qarz: 11_500_000 },
  { kun: '05', daromad: 160_000_000, xarajat: 34_500_000, foyda: 125_500_000, qarz: 10_800_000 },
  { kun: '06', daromad: 178_000_000, xarajat: 36_700_000, foyda: 141_300_000, qarz: 9_900_000  },
  { kun: '07', daromad: 211_000_000, xarajat: 41_000_000, foyda: 170_000_000, qarz: 14_000_000 },
];

const buOy: MockPeriodData = {
  kpi: {
    daromad: 1_000_000_000,
    foyda: 803_200_000,
    marja: 77.5,
    xarajat: 232_700_000,
    qarz: 14_000_000,
    faolOquvchi: 23,
    konversiya: 15.3,
    daromadDelta: 100,
    foydaDelta: 84.2,
    xarajatDelta: 12.4,
    qarzDelta: -1.4,
    faolOquvchiDelta: 9.5,
    konversiyaDelta: 3.2,
  },
  daily: buOyDaily,
  payment: {
    completed: 17,
    pending: 61,
    overdue: 22,
    total: 1_000_000_000,
    ortachaTolov: 265_000,
    tolovBajarildi: 170_000_000,
    daromadSifati: 87.3,
    qaytaTolov: 3_200_000,
  },
  teachers: [
    { id: 1, ism: 'Aziz Karimov',     guruhlar: 4, oquvchilar: 48, daromad: 312_000_000, marja: 81.2, baho: 4.9 },
    { id: 2, ism: 'Nilufar Yusupova', guruhlar: 3, oquvchilar: 35, daromad: 241_000_000, marja: 76.4, baho: 4.7 },
    { id: 3, ism: 'Bobur Toshev',     guruhlar: 5, oquvchilar: 61, daromad: 447_000_000, marja: 79.1, baho: 4.8 },
    { id: 4, ism: 'Malika Raximova',  guruhlar: 2, oquvchilar: 22, daromad: 148_000_000, marja: 72.3, baho: 4.5 },
    { id: 5, ism: 'Jasur Holiqov',    guruhlar: 3, oquvchilar: 39, daromad: 275_000_000, marja: 74.8, baho: 4.6 },
  ],
  groups: [
    { id: 1, nom: 'Python Pro',       ustoz: 'Aziz Karimov',     bolim: 'IT',     oquvchilar: 18, daromad: 162_000_000, status: 'aktiv'    },
    { id: 2, nom: 'Web Dev Advance',  ustoz: 'Bobur Toshev',     bolim: 'IT',     oquvchilar: 22, daromad: 198_000_000, status: 'aktiv'    },
    { id: 3, nom: 'SMM & Marketing',  ustoz: 'Nilufar Yusupova', bolim: 'Biznes', oquvchilar: 14, daromad:  98_000_000, status: 'yangi'    },
    { id: 4, nom: 'Grafik Dizayn',    ustoz: 'Malika Raximova',  bolim: 'Dizayn', oquvchilar: 11, daromad:  77_000_000, status: 'aktiv'    },
    { id: 5, nom: 'Flutter Bootcamp', ustoz: 'Jasur Holiqov',    bolim: 'IT',     oquvchilar: 16, daromad: 144_000_000, status: 'toxtagan' },
  ],
  funnel: [
    { nom: 'Murojaat',      son: 340, foiz: 100, color: '#22d3ee' },
    { nom: "Qo'ng'iroq",   son: 218, foiz: 64,  color: '#818cf8' },
    { nom: 'Sinov darsi',  son: 142, foiz: 42,  color: '#a78bfa' },
    { nom: "Ro'yxatdan",   son:  87, foiz: 26,  color: '#34d399' },
    { nom: "To'lov",       son:  52, foiz: 15,  color: '#f59e0b' },
  ],
  goals: [
    { nom: 'Oylik daromad',   maqsad: 1_500_000_000, hozir: 1_000_000_000, birlik: 'UZS'   },
    { nom: "Yangi o'quvchi",  maqsad: 50,            hozir: 23,             birlik: 'kishi' },
    { nom: 'Konversiya',      maqsad: 30,            hozir: 15,             birlik: '%'     },
    { nom: 'NPS ball',        maqsad: 90,            hozir: 84,             birlik: 'ball'  },
  ],
};

/* ─── O'TGAN OY ──────────────────────────────────────────────────────────────── */
const otganOyDaily: DailyPoint[] = [
  { kun: '01', daromad: 55_000_000, xarajat: 27_000_000, foyda: 28_000_000, qarz: 18_000_000 },
  { kun: '05', daromad: 68_000_000, xarajat: 29_000_000, foyda: 39_000_000, qarz: 17_200_000 },
  { kun: '10', daromad: 74_000_000, xarajat: 31_000_000, foyda: 43_000_000, qarz: 16_400_000 },
  { kun: '15', daromad: 82_000_000, xarajat: 28_000_000, foyda: 54_000_000, qarz: 15_800_000 },
  { kun: '20', daromad: 91_000_000, xarajat: 32_000_000, foyda: 59_000_000, qarz: 16_100_000 },
  { kun: '25', daromad: 78_000_000, xarajat: 30_000_000, foyda: 48_000_000, qarz: 15_500_000 },
  { kun: '31', daromad: 52_000_000, xarajat: 26_000_000, foyda: 26_000_000, qarz: 14_200_000 },
];

const otganOy: MockPeriodData = {
  kpi: {
    daromad: 500_000_000,
    foyda: 435_800_000,
    marja: 62.1,
    xarajat: 207_000_000,
    qarz: 18_200_000,
    faolOquvchi: 21,
    konversiya: 12.1,
    daromadDelta: -8.4,
    foydaDelta: -11.3,
    xarajatDelta: -2.1,
    qarzDelta: 4.1,
    faolOquvchiDelta: -4.5,
    konversiyaDelta: -1.8,
  },
  daily: otganOyDaily,
  payment: {
    completed: 12,
    pending: 66,
    overdue: 22,
    total: 500_000_000,
    ortachaTolov: 198_000,
    tolovBajarildi: 60_000_000,
    daromadSifati: 79.1,
    qaytaTolov: 5_800_000,
  },
  teachers: [
    { id: 1, ism: 'Aziz Karimov',     guruhlar: 3, oquvchilar: 41, daromad: 214_000_000, marja: 71.2, baho: 4.7 },
    { id: 2, ism: 'Nilufar Yusupova', guruhlar: 2, oquvchilar: 28, daromad: 142_000_000, marja: 68.4, baho: 4.6 },
    { id: 3, ism: 'Bobur Toshev',     guruhlar: 4, oquvchilar: 52, daromad: 318_000_000, marja: 71.8, baho: 4.7 },
    { id: 4, ism: 'Malika Raximova',  guruhlar: 2, oquvchilar: 18, daromad: 121_000_000, marja: 64.1, baho: 4.4 },
    { id: 5, ism: 'Jasur Holiqov',    guruhlar: 2, oquvchilar: 31, daromad: 187_000_000, marja: 67.2, baho: 4.5 },
  ],
  groups: [
    { id: 1, nom: 'Python Pro',       ustoz: 'Aziz Karimov',     bolim: 'IT',     oquvchilar: 16, daromad: 122_000_000, status: 'aktiv' },
    { id: 2, nom: 'Web Dev Advance',  ustoz: 'Bobur Toshev',     bolim: 'IT',     oquvchilar: 19, daromad: 142_000_000, status: 'aktiv' },
    { id: 3, nom: 'SMM & Marketing',  ustoz: 'Nilufar Yusupova', bolim: 'Biznes', oquvchilar: 11, daromad:  71_000_000, status: 'aktiv' },
    { id: 4, nom: 'Grafik Dizayn',    ustoz: 'Malika Raximova',  bolim: 'Dizayn', oquvchilar:  9, daromad:  58_000_000, status: 'aktiv' },
    { id: 5, nom: 'Flutter Bootcamp', ustoz: 'Jasur Holiqov',    bolim: 'IT',     oquvchilar: 14, daromad: 107_000_000, status: 'aktiv' },
  ],
  funnel: [
    { nom: 'Murojaat',      son: 210, foiz: 100, color: '#22d3ee' },
    { nom: "Qo'ng'iroq",   son: 134, foiz: 64,  color: '#818cf8' },
    { nom: 'Sinov darsi',  son:  88, foiz: 42,  color: '#a78bfa' },
    { nom: "Ro'yxatdan",   son:  54, foiz: 26,  color: '#34d399' },
    { nom: "To'lov",       son:  31, foiz: 15,  color: '#f59e0b' },
  ],
  goals: [
    { nom: 'Oylik daromad',   maqsad: 1_500_000_000, hozir: 500_000_000, birlik: 'UZS'   },
    { nom: "Yangi o'quvchi",  maqsad: 50,            hozir: 21,           birlik: 'kishi' },
    { nom: 'Konversiya',      maqsad: 30,            hozir: 12,           birlik: '%'     },
    { nom: 'NPS ball',        maqsad: 90,            hozir: 78,           birlik: 'ball'  },
  ],
};

export const mockData: Record<Period, MockPeriodData> = {
  bu_oy: buOy,
  otgan_oy: otganOy,
};

/* ─── Format helpers ─────────────────────────────────────────────────────────── */
export function formatUZS(value: number): string {
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)} mlrd UZS`;
  if (value >= 1_000_000)     return `${(value / 1_000_000).toFixed(1)} mln UZS`;
  if (value >= 1_000)         return `${(value / 1_000).toFixed(0)} ming UZS`;
  return `${value} UZS`;
}

export function formatCompact(value: number): string {
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}mlrd`;
  if (value >= 1_000_000)     return `${(value / 1_000_000).toFixed(1)}mln`;
  if (value >= 1_000)         return `${(value / 1_000).toFixed(0)}ming`;
  return `${value}`;
}
