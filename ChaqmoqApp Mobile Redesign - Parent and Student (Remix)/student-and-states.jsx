// ============================================================
// ChaqmoqApp — Student screens (dark, teal-forward) + States
// ============================================================

// ---- 10 Student Dashboard ----
function StudentDashboard({ onOpenScreen, offline = false }) {
  const activity = [3, 5, 4, 7, 6, 8, 5, 9, 7, 6, 8, 9];

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative', background: 'var(--s-bg-gradient)', color: 'var(--s-text)' }}>
      <StatusBar dark />
      {/* atmospheric blob */}
      <div style={{ position: 'absolute', top: 60, right: -60, width: 220, height: 220, borderRadius: '50%', background: 'radial-gradient(circle, rgba(0,212,170,0.22), transparent 70%)', filter: 'blur(40px)', pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', top: 220, left: -60, width: 200, height: 200, borderRadius: '50%', background: 'radial-gradient(circle, rgba(108,99,255,0.18), transparent 70%)', filter: 'blur(40px)', pointerEvents: 'none' }} />

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 18px 12px', position: 'relative', zIndex: 2 }}>
        <ChaqmoqMark size={36} dark />
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 11, color: 'var(--s-text-muted)', fontWeight: 600 }}>ChaqmoqApp ⚡</div>
          <div style={{ fontSize: 14, fontWeight: 800 }}>O'quvchi paneli</div>
        </div>
        <button style={{ ...iconBtnDark, position: 'relative' }} onClick={() => onOpenScreen && onOpenScreen('notif')}>
          <span className="material-symbols-rounded" style={{ fontSize: 22 }}>notifications</span>
          <span style={{ position: 'absolute', top: 7, right: 7, minWidth: 14, height: 14, borderRadius: 100, background: 'var(--s-danger)', color: '#fff', fontSize: 9, fontWeight: 800, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: '0 3px', border: '2px solid #0A0A0F' }}>2</span>
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 18px 110px', position: 'relative', zIndex: 2 }} className="no-scrollbar">

        {/* Offline notice */}
        {offline && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '10px 12px', borderRadius: 14,
            background: 'rgba(255,165,2,0.10)', border: '1px solid rgba(255,165,2,0.32)',
            color: '#FFA502', marginBottom: 12,
          }}>
            <span className="material-symbols-rounded" style={{ fontSize: 18 }}>cloud_off</span>
            <span style={{ fontSize: 12, fontWeight: 700, flex: 1 }}>Oflayn rejim · oxirgi ma'lumot 12 daq oldin</span>
          </div>
        )}

        {/* Hero */}
        <div style={{
          background: 'var(--s-hero-gradient)',
          border: '1px solid rgba(0,212,170,0.22)',
          borderRadius: 24, padding: 18, marginBottom: 14,
          position: 'relative', overflow: 'hidden',
        }}>
          <div style={{ position: 'absolute', top: -30, right: -30, width: 130, height: 130, borderRadius: '50%', background: 'radial-gradient(circle, rgba(0,212,170,0.30), transparent 70%)' }} />
          <div style={{ fontSize: 11, color: 'var(--s-primary)', fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', position: 'relative' }}>O'quvchi paneli</div>
          <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.01em', marginTop: 4, position: 'relative' }}>Salom, Ali 👋</div>
          <div style={{ fontSize: 12.5, color: 'var(--s-text-muted)', fontWeight: 500, marginTop: 4, position: 'relative' }}>ProSkill Academy · IELTS A1</div>

          <div style={{ display: 'flex', gap: 8, marginTop: 14, position: 'relative' }}>
            {[
              { i: 'payments', l: "To'lovlar", id: 'pay' },
              { i: 'forum', l: 'Xabarlar', id: 'msg' },
              { i: 'person', l: 'Profil', id: 'profile' },
            ].map(qa => (
              <button key={qa.l} onClick={() => onOpenScreen && onOpenScreen(qa.id)} style={{
                flex: 1,
                background: 'var(--s-glass-strong)', border: '1px solid var(--s-border-strong)',
                borderRadius: 14, padding: '10px 6px',
                color: 'var(--s-text)', fontFamily: 'inherit',
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
                cursor: 'pointer',
              }}>
                <span className="material-symbols-rounded" style={{ fontSize: 18, color: 'var(--s-primary)' }}>{qa.i}</span>
                <span style={{ fontSize: 11, fontWeight: 700 }}>{qa.l}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Chaqmoq rating card */}
        <GCard padding={16} style={{ marginBottom: 14, position: 'relative', overflow: 'hidden', border: '1px solid rgba(108,99,255,0.32)' }}>
          <div style={{ position: 'absolute', top: -30, right: -30, width: 110, height: 110, borderRadius: '50%', background: 'radial-gradient(circle, rgba(108,99,255,0.32), transparent 70%)' }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, position: 'relative' }}>
            <div style={{
              width: 64, height: 64, borderRadius: '50%',
              background: 'linear-gradient(135deg, #6C63FF, #00D4AA)',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 10px 24px rgba(108,99,255,0.35)',
            }}>
              <span className="material-symbols-rounded msr-fill" style={{ fontSize: 32, color: '#fff' }}>bolt</span>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 11, color: 'var(--s-text-muted)', fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase' }}>Chaqmoq reyting</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 2 }}>
                <span style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-0.02em' }}>2 184</span>
                <span style={{ fontSize: 12, color: 'var(--s-text-muted)', fontWeight: 600 }}>ball</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                <Badge tone="success" dark>#4 reyting</Badge>
                <span style={{ fontSize: 11, color: 'var(--s-success)', fontWeight: 700 }}>+142 hafta</span>
              </div>
            </div>
          </div>
        </GCard>

        {/* Metrics */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
          {[
            { i: 'fact_check', l: 'Davomat', v: '92%', sub: '20 / 22 dars', tone: 'teal' },
            { i: 'account_balance_wallet', l: 'Qarzdorlik', v: '0', sub: "0 so'm · toza", tone: 'success' },
            { i: 'grade', l: "O'rtacha ball", v: '4.7', sub: '+0.3 oy ichida', tone: 'violet' },
            { i: 'trending_up', l: 'Faollik', v: '8.4', sub: 'Hafta ko\'rsatkichi', tone: 'amber' },
          ].map((m, i) => {
            const tones = {
              teal:    { bg: 'rgba(0,212,170,0.16)', fg: 'var(--s-primary)' },
              violet:  { bg: 'rgba(108,99,255,0.18)', fg: 'var(--s-secondary-soft)' },
              success: { bg: 'rgba(46,213,115,0.16)', fg: 'var(--s-success)' },
              amber:   { bg: 'rgba(255,165,2,0.16)', fg: 'var(--s-warning)' },
            };
            const t = tones[m.tone];
            return (
              <GCard key={i} padding={14}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ width: 32, height: 32, borderRadius: 10, background: t.bg, color: t.fg, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
                    <span className="material-symbols-rounded" style={{ fontSize: 18 }}>{m.i}</span>
                  </span>
                </div>
                <div style={{ fontSize: 11, color: 'var(--s-text-muted)', fontWeight: 600, marginTop: 8 }}>{m.l}</div>
                <div style={{ fontSize: 19, fontWeight: 800, letterSpacing: '-0.02em' }}>{m.v}</div>
                <div style={{ fontSize: 10.5, color: 'var(--s-text-muted)', fontWeight: 600, marginTop: 2 }}>{m.sub}</div>
              </GCard>
            );
          })}
        </div>

        {/* Activity card */}
        <GCard padding={16}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 800 }}>Faollik · 12 hafta</div>
            <Badge tone="teal" dark>+18%</Badge>
          </div>
          <MiniBars data={activity} labels={['1','2','3','4','5','6','7','8','9','10','11','12']} color="var(--s-primary)" height={70} max={10} />
        </GCard>
      </div>

      <StudentBottomNav active="panel" onChange={(id) => onOpenScreen && onOpenScreen(id)} />
    </div>
  );
}

// ---- 11 Student Payments ----
const SPAYMENTS = [
  { id: 1, month: 'May 2026', amount: 850000, status: 'pending', due: '15-may' },
  { id: 2, month: 'Apr 2026', amount: 850000, status: 'paid', date: '12-apr', method: 'Click' },
  { id: 3, month: 'Mar 2026', amount: 850000, status: 'paid', date: '14-mar', method: 'Payme' },
  { id: 4, month: 'Fev 2026', amount: 850000, status: 'paid', date: '10-fev', method: 'Click' },
  { id: 5, month: 'Yan 2026', amount: 850000, status: 'paid', date: '08-yan', method: 'Naqd' },
];

function StudentPayments({ onOpenScreen }) {
  const [filter, setFilter] = useState('all');
  const filtered = SPAYMENTS.filter(p =>
    filter === 'all' ? true : filter === 'paid' ? p.status === 'paid' : p.status !== 'paid'
  );
  const totalPaid = SPAYMENTS.filter(p => p.status === 'paid').reduce((a, b) => a + b.amount, 0);

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative', background: 'var(--s-bg-gradient)', color: 'var(--s-text)' }}>
      <StatusBar dark />
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 18px 14px' }}>
        <h1 style={{ fontSize: 19, fontWeight: 800, margin: 0, flex: 1, letterSpacing: '-0.01em' }}>To'lovlar</h1>
        <button style={iconBtnDark}>
          <span className="material-symbols-rounded" style={{ fontSize: 22 }}>history</span>
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '0 18px 110px' }} className="no-scrollbar">

        {/* Hero */}
        <div style={{
          background: 'linear-gradient(135deg, rgba(0,212,170,0.20), rgba(108,99,255,0.16))',
          border: '1px solid rgba(0,212,170,0.28)',
          borderRadius: 24, padding: 18, marginBottom: 14,
          position: 'relative', overflow: 'hidden',
        }}>
          <div style={{ position: 'absolute', top: -40, right: -40, width: 150, height: 150, borderRadius: '50%', background: 'radial-gradient(circle, rgba(0,212,170,0.32), transparent 70%)' }} />
          <div style={{ fontSize: 11, color: 'var(--s-primary)', fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', position: 'relative' }}>Joriy holat</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 4, position: 'relative' }}>
            <span style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums' }}>0</span>
            <span style={{ fontSize: 13, color: 'var(--s-text-muted)', fontWeight: 600 }}>so'm qarzdorlik</span>
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--s-text-muted)', fontWeight: 600, marginTop: 4, position: 'relative' }}>
            Keyingi to'lov: 15-may · 850 000 so'm
          </div>
        </div>

        {/* Mini cards */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 14 }}>
          {[
            { l: "Jami to'langan", v: fmtSomShort(totalPaid), c: 'var(--s-primary)' },
            { l: 'Bu oy', v: '0', c: 'var(--s-text)' },
            { l: 'Qarzdorlik', v: '0', c: 'var(--s-success)' },
          ].map((s, i) => (
            <GCard key={i} padding={12}>
              <div style={{ fontSize: 10, color: 'var(--s-text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{s.l}</div>
              <div style={{ fontSize: 16, fontWeight: 800, color: s.c, marginTop: 4, letterSpacing: '-0.02em' }}>{s.v}</div>
            </GCard>
          ))}
        </div>

        {/* Filter chips */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          {[
            { id: 'all', l: 'Barchasi' },
            { id: 'paid', l: "To'langan" },
            { id: 'debt', l: 'Qarzlar' },
          ].map(c => (
            <button key={c.id} onClick={() => setFilter(c.id)} style={{
              padding: '7px 14px', borderRadius: 100,
              background: filter === c.id ? 'var(--s-primary)' : 'var(--s-glass)',
              color: filter === c.id ? '#0A1F1A' : 'var(--s-text-muted)',
              border: filter === c.id ? 0 : '1px solid var(--s-border)',
              fontFamily: 'inherit', fontWeight: 700, fontSize: 12,
              cursor: 'pointer',
            }}>{c.l}</button>
          ))}
        </div>

        {filtered.map(p => (
          <GCard key={p.id} padding={14} style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 42, height: 42, borderRadius: 12,
              background: p.status === 'paid' ? 'rgba(46,213,115,0.16)' : 'rgba(255,165,2,0.16)',
              color: p.status === 'paid' ? 'var(--s-success)' : 'var(--s-warning)',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <span className="material-symbols-rounded" style={{ fontSize: 22 }}>{p.status === 'paid' ? 'check_circle' : 'schedule'}</span>
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13.5, fontWeight: 800 }}>{p.month}</div>
              <div style={{ fontSize: 11, color: 'var(--s-text-muted)', fontWeight: 600, marginTop: 2 }}>
                {p.status === 'paid' ? `${p.method} · ${p.date}` : `Muddat: ${p.due}`}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 14, fontWeight: 800, fontVariantNumeric: 'tabular-nums' }}>{fmtSomShort(p.amount)}</div>
              <div style={{ fontSize: 10, color: 'var(--s-text-muted)', fontWeight: 600 }}>so'm</div>
            </div>
          </GCard>
        ))}
      </div>

      <StudentBottomNav active="pay" onChange={(id) => onOpenScreen && onOpenScreen(id)} />
    </div>
  );
}

// ---- 12 Notifications ----
const NOTIFS = [
  { id: 1, type: 'pay', title: "Yangi to'lov muddati", body: "May oyi to'lovi 15-mayga qoldi. 850 000 so'm.", time: '5 daq', unread: true, icon: 'payments' },
  { id: 2, type: 'attend', title: 'Bugungi dars boshlandi', body: 'IELTS Speaking · 15:00 — 16:30. Ali davomatda.', time: '1 soat', unread: true, icon: 'fact_check' },
  { id: 3, type: 'progress', title: "Yangi natija qo'shildi", body: 'Mock test #4: 4.8 / 5 — eng yaxshi natija!', time: '3 soat', unread: false, icon: 'grade' },
  { id: 4, type: 'msg', title: 'Aziz domla xabar yubordi', body: '"Uyga vazifa: Cambridge 17, Test 2 — Part 2."', time: '1 kun', unread: false, icon: 'forum' },
  { id: 5, type: 'system', title: 'Profil yangilandi', body: "Telefon raqami muvaffaqiyatli o'zgartirildi.", time: '3 kun', unread: false, icon: 'check_circle' },
];

function NotificationsScreen({ onBack, dark = false, onOpenDetail }) {
  const palette = dark ? {
    bg: 'var(--s-bg-gradient)', text: 'var(--s-text)', muted: 'var(--s-text-muted)',
    cardBg: 'var(--s-glass)', cardBorder: 'var(--s-border)', accent: 'var(--s-primary)',
    iconBg: 'rgba(0,212,170,0.16)', iconFg: 'var(--s-primary)',
    unreadDot: 'var(--s-primary)',
  } : {
    bg: 'var(--p-bg)', text: 'var(--p-text)', muted: 'var(--p-text-muted)',
    cardBg: 'var(--p-card)', cardBorder: 'var(--p-line)', accent: 'var(--p-primary)',
    iconBg: 'var(--p-info-bg)', iconFg: 'var(--p-primary-deep)',
    unreadDot: 'var(--p-primary)',
  };
  const unread = NOTIFS.filter(n => n.unread).length;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: palette.bg, color: palette.text }}>
      <StatusBar dark={dark} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 18px 14px' }}>
        <button onClick={onBack} style={dark ? iconBtnDark : iconBtnLight}>
          <span className="material-symbols-rounded" style={{ fontSize: 22 }}>arrow_back</span>
        </button>
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 19, fontWeight: 800, margin: 0, letterSpacing: '-0.01em' }}>Bildirishnomalar</h1>
          <div style={{ fontSize: 11.5, color: palette.muted, fontWeight: 600, marginTop: 1 }}>{unread} yangi</div>
        </div>
        <button style={{ ...(dark ? iconBtnDark : iconBtnLight), width: 'auto', padding: '0 12px', gap: 6 }}>
          <span className="material-symbols-rounded" style={{ fontSize: 18 }}>done_all</span>
          <span style={{ fontSize: 12, fontWeight: 700 }}>Hammasi</span>
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '0 18px 28px' }} className="no-scrollbar">
        {NOTIFS.map(n => (
          <div key={n.id} onClick={() => onOpenDetail && onOpenDetail(n)} style={{
            background: n.unread ? (dark ? 'rgba(0,212,170,0.06)' : 'var(--p-primary-tint)') : palette.cardBg,
            border: `1px solid ${n.unread ? (dark ? 'rgba(0,212,170,0.20)' : '#BFDBFE') : palette.cardBorder}`,
            borderRadius: 18, padding: 14,
            display: 'flex', gap: 12, alignItems: 'flex-start',
            marginBottom: 8, cursor: 'pointer',
            position: 'relative',
          }}>
            <span style={{
              width: 40, height: 40, borderRadius: 12,
              background: palette.iconBg, color: palette.iconFg,
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            }}>
              <span className="material-symbols-rounded" style={{ fontSize: 22 }}>{n.icon}</span>
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                <span style={{ fontSize: 13.5, fontWeight: 800 }}>{n.title}</span>
                <span style={{ fontSize: 10.5, color: palette.muted, fontWeight: 600, flexShrink: 0 }}>{n.time}</span>
              </div>
              <div style={{ fontSize: 12, color: palette.muted, fontWeight: 500, lineHeight: 1.45, marginTop: 4 }}>{n.body}</div>
            </div>
            {n.unread && <span style={{ position: 'absolute', top: 14, right: 14, width: 8, height: 8, borderRadius: '50%', background: palette.unreadDot }} />}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---- 13 Notification detail (sheet) ----
function NotificationDetailSheet({ notif, onClose, dark = false }) {
  if (!notif) return null;
  return (
    <BottomSheet title="Bildirishnoma" onClose={onClose} dark={dark}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
        <span style={{
          width: 50, height: 50, borderRadius: 14,
          background: dark ? 'rgba(0,212,170,0.16)' : 'var(--p-info-bg)',
          color: dark ? 'var(--s-primary)' : 'var(--p-primary-deep)',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <span className="material-symbols-rounded" style={{ fontSize: 26 }}>{notif.icon}</span>
        </span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 16, fontWeight: 800 }}>{notif.title}</div>
          <div style={{ fontSize: 11.5, color: dark ? 'var(--s-text-muted)' : 'var(--p-text-muted)', fontWeight: 600, marginTop: 2 }}>{notif.time} oldin · ProSkill Academy</div>
        </div>
      </div>
      <div style={{ fontSize: 13.5, lineHeight: 1.55, color: dark ? 'var(--s-text)' : 'var(--p-text-soft)', marginBottom: 16 }}>
        {notif.body} Iltimos, eslatma muddatigacha to'lovni amalga oshirsangiz, qo'shimcha bildirishnoma kelmaydi.
      </div>
      {notif.type === 'pay' && (
        <div style={{
          padding: 14, borderRadius: 16,
          background: dark ? 'var(--s-glass)' : 'var(--p-bg-soft)',
          border: dark ? '1px solid var(--s-border)' : '1px solid var(--p-line)',
          marginBottom: 14,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontWeight: 700, marginBottom: 8 }}>
            <span style={{ color: dark ? 'var(--s-text-muted)' : 'var(--p-text-muted)' }}>Summa</span>
            <span>850 000 so'm</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontWeight: 700, marginBottom: 8 }}>
            <span style={{ color: dark ? 'var(--s-text-muted)' : 'var(--p-text-muted)' }}>Muddat</span>
            <span>15-may, 2026</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontWeight: 700 }}>
            <span style={{ color: dark ? 'var(--s-text-muted)' : 'var(--p-text-muted)' }}>O'quvchi</span>
            <span>Ali Karimov</span>
          </div>
        </div>
      )}
      <PButton icon={notif.type === 'pay' ? 'credit_card' : 'arrow_forward'} dark={dark}>
        {notif.type === 'pay' ? "To'lovga o'tish" : "Ko'rib chiqish"}
      </PButton>
    </BottomSheet>
  );
}

// ---- 14 Student Account / Profile ----
function StudentAccount({ onOpenScreen }) {
  const settings = [
    { i: 'edit', l: 'Profilni tahrirlash' },
    { i: 'lock', l: 'Xavfsizlik' },
    { i: 'notifications', l: 'Bildirishnomalar', val: 'Yoqilgan' },
    { i: 'language', l: 'Til', val: "O'zbek" },
    { i: 'help', l: "Yordam" },
    { i: 'info', l: 'Ilova haqida', val: 'v2.4.1' },
  ];

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--s-bg-gradient)', color: 'var(--s-text)', position: 'relative' }}>
      <StatusBar dark />
      <div style={{ position: 'absolute', top: 80, left: -50, width: 180, height: 180, borderRadius: '50%', background: 'radial-gradient(circle, rgba(108,99,255,0.18), transparent 70%)', filter: 'blur(40px)', pointerEvents: 'none' }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 18px 14px', position: 'relative' }}>
        <h1 style={{ fontSize: 19, fontWeight: 800, margin: 0, flex: 1, letterSpacing: '-0.01em' }}>Profil</h1>
        <button style={iconBtnDark}><span className="material-symbols-rounded" style={{ fontSize: 22 }}>settings</span></button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '0 18px 110px', position: 'relative' }} className="no-scrollbar">

        {/* Hero card */}
        <GCard padding={20} style={{
          textAlign: 'center', marginBottom: 14,
          background: 'linear-gradient(135deg, rgba(108,99,255,0.18), rgba(0,212,170,0.10) 60%, rgba(255,255,255,0.02))',
          border: '1px solid rgba(108,99,255,0.28)',
          position: 'relative', overflow: 'hidden',
        }}>
          <div style={{ position: 'absolute', top: -40, right: -40, width: 140, height: 140, borderRadius: '50%', background: 'radial-gradient(circle, rgba(0,212,170,0.20), transparent 70%)' }} />
          <div style={{ display: 'inline-block', position: 'relative', marginBottom: 10 }}>
            <Avatar name="Ali Karimov" size={84} color="violet" />
            <span style={{ position: 'absolute', right: -2, bottom: -2, width: 26, height: 26, borderRadius: '50%', background: 'var(--s-primary)', color: '#0A1F1A', border: '3px solid #13131A', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
              <span className="material-symbols-rounded msr-fill" style={{ fontSize: 14 }}>bolt</span>
            </span>
          </div>
          <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.01em' }}>Ali Karimov</div>
          <div style={{ marginTop: 6, display: 'inline-flex' }}>
            <Badge tone="violet" dark>O'quvchi · IELTS A1</Badge>
          </div>
        </GCard>

        {/* Info rows */}
        <GCard padding={4} style={{ marginBottom: 14 }}>
          {[
            { i: 'apartment', l: 'Markaz', v: 'ProSkill Academy' },
            { i: 'mail', l: 'Email', v: 'ali.karimov@example.uz' },
            { i: 'phone', l: 'Telefon', v: '+998 90 555 12 34' },
            { i: 'event', l: "Qo'shilgan", v: '12 Sen 2024' },
          ].map((r, i, a) => (
            <div key={r.i} style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '12px',
              borderBottom: i < a.length - 1 ? '1px solid var(--s-border)' : 'none',
            }}>
              <span style={{
                width: 32, height: 32, borderRadius: 10,
                background: 'rgba(0,212,170,0.14)', color: 'var(--s-primary)',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <span className="material-symbols-rounded" style={{ fontSize: 16 }}>{r.i}</span>
              </span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 11, color: 'var(--s-text-muted)', fontWeight: 600 }}>{r.l}</div>
                <div style={{ fontSize: 13, fontWeight: 700, marginTop: 1 }}>{r.v}</div>
              </div>
            </div>
          ))}
        </GCard>

        <div style={{ fontSize: 13, fontWeight: 800, color: 'var(--s-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Sozlamalar</div>
        <GCard padding={4}>
          {settings.map((s, i) => (
            <div key={s.i} style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '12px',
              borderBottom: i < settings.length - 1 ? '1px solid var(--s-border)' : 'none',
              cursor: 'pointer',
            }}>
              <span style={{
                width: 32, height: 32, borderRadius: 10,
                background: 'var(--s-glass-strong)', color: 'var(--s-primary)',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <span className="material-symbols-rounded" style={{ fontSize: 16 }}>{s.i}</span>
              </span>
              <span style={{ flex: 1, fontSize: 13.5, fontWeight: 600 }}>{s.l}</span>
              {s.val && <span style={{ fontSize: 11.5, color: 'var(--s-text-muted)', fontWeight: 600 }}>{s.val}</span>}
              <span className="material-symbols-rounded" style={{ fontSize: 18, color: 'var(--s-text-dim)' }}>chevron_right</span>
            </div>
          ))}
        </GCard>

        <button style={{
          width: '100%', marginTop: 14,
          padding: 14, borderRadius: 16,
          background: 'rgba(255,71,87,0.10)', color: 'var(--s-danger)',
          border: '1px solid rgba(255,71,87,0.28)',
          fontFamily: 'inherit', fontWeight: 700, fontSize: 13.5,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          cursor: 'pointer',
        }}>
          <span className="material-symbols-rounded" style={{ fontSize: 20 }}>logout</span>
          Chiqish
        </button>
      </div>

      <StudentBottomNav active="profile" onChange={(id) => onOpenScreen && onOpenScreen(id)} />
    </div>
  );
}

// ---- 15 States: Loading / Empty / Error / Offline ----
function LoadingState({ light = true }) {
  const bg = light ? 'var(--p-bg)' : '#0A0A0F';
  const card = light ? 'var(--p-card)' : 'var(--s-glass)';
  const line = light ? 'var(--p-line)' : 'var(--s-border)';
  const shimmer = light ? 'linear-gradient(90deg, #EAF1F9 0%, #F4F7FB 50%, #EAF1F9 100%)' : 'linear-gradient(90deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.10) 50%, rgba(255,255,255,0.04) 100%)';
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: bg, color: light ? 'var(--p-text)' : 'var(--s-text)' }}>
      <StatusBar dark={!light} />
      <div style={{ padding: '12px 18px 0' }}>
        <div style={{ height: 24, width: 140, background: shimmer, borderRadius: 8, backgroundSize: '200% 100%', animation: 'shimmer 1.4s linear infinite', marginBottom: 10 }} />
        <div style={{ height: 14, width: 200, background: shimmer, borderRadius: 8, backgroundSize: '200% 100%', animation: 'shimmer 1.4s linear infinite', marginBottom: 18 }} />
      </div>
      <div style={{ padding: '0 18px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {[120, 90, 70, 70, 90].map((h, i) => (
          <div key={i} style={{
            height: h, background: card, border: `1px solid ${line}`,
            borderRadius: 18,
            position: 'relative', overflow: 'hidden',
          }}>
            <div style={{ position: 'absolute', inset: 0, background: shimmer, backgroundSize: '200% 100%', animation: 'shimmer 1.4s linear infinite', opacity: 0.6 }} />
          </div>
        ))}
      </div>
    </div>
  );
}

function EmptyState({ light = true }) {
  const bg = light ? 'var(--p-bg)' : '#0A0A0F';
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: bg, color: light ? 'var(--p-text)' : 'var(--s-text)' }}>
      <StatusBar dark={!light} />
      <ParentAppBar title="To'lovlar" onBack={() => {}} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '0 32px', textAlign: 'center', marginTop: -40 }}>
        <div style={{
          width: 100, height: 100, borderRadius: 32,
          background: light ? 'var(--p-primary-tint)' : 'rgba(0,212,170,0.10)',
          color: light ? 'var(--p-primary)' : 'var(--s-primary)',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: 18,
        }}>
          <span className="material-symbols-rounded" style={{ fontSize: 48 }}>inbox</span>
        </div>
        <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.01em', marginBottom: 6 }}>Hozircha to'lov yo'q</div>
        <div style={{ fontSize: 13, color: light ? 'var(--p-text-muted)' : 'var(--s-text-muted)', fontWeight: 500, lineHeight: 1.5, maxWidth: 260, marginBottom: 18 }}>
          Yangi hisob-kitoblar paydo bo'lganda, ular shu yerda ko'rinadi.
        </div>
        <PButton icon="refresh" full={false}>Yangilash</PButton>
      </div>
    </div>
  );
}

function ErrorState({ light = true }) {
  const bg = light ? 'var(--p-bg)' : '#0A0A0F';
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: bg, color: light ? 'var(--p-text)' : 'var(--s-text)' }}>
      <StatusBar dark={!light} />
      <ParentAppBar title="Progress" onBack={() => {}} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '0 32px', textAlign: 'center', marginTop: -40 }}>
        <div style={{
          width: 100, height: 100, borderRadius: 32,
          background: light ? 'var(--p-danger-bg)' : 'rgba(255,71,87,0.12)',
          color: light ? 'var(--p-danger)' : 'var(--s-danger)',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: 18,
        }}>
          <span className="material-symbols-rounded" style={{ fontSize: 48 }}>error</span>
        </div>
        <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.01em', marginBottom: 6 }}>Ma'lumot yuklanmadi</div>
        <div style={{ fontSize: 13, color: light ? 'var(--p-text-muted)' : 'var(--s-text-muted)', fontWeight: 500, lineHeight: 1.5, maxWidth: 280, marginBottom: 18 }}>
          Internet aloqasi yo'q yoki server vaqtinchalik javob bermayapti. Iltimos, qaytadan urinib ko'ring.
        </div>
        <PButton icon="refresh" full={false}>Qayta urinish</PButton>
      </div>
    </div>
  );
}

function OfflineState({ light = true }) {
  const bg = light ? 'var(--p-bg)' : '#0A0A0F';
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: bg, color: light ? 'var(--p-text)' : 'var(--s-text)' }}>
      <StatusBar dark={!light} />
      <ParentAppBar title="Bosh sahifa" />
      <div style={{ padding: '0 18px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '12px 14px', borderRadius: 16,
          background: light ? 'var(--p-amber-bg)' : 'rgba(255,165,2,0.10)',
          border: `1px solid ${light ? '#FDE68A' : 'rgba(255,165,2,0.32)'}`,
          color: light ? 'var(--p-amber-deep)' : 'var(--s-warning)',
          marginBottom: 14,
        }}>
          <span className="material-symbols-rounded" style={{ fontSize: 22 }}>cloud_off</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 800 }}>Oflayn rejim</div>
            <div style={{ fontSize: 11.5, fontWeight: 600, marginTop: 2, opacity: 0.85 }}>Oxirgi sinxronizatsiya: 12 daq oldin</div>
          </div>
        </div>

        <PCard padding={16} style={{ marginBottom: 10, opacity: 0.85 }}>
          <div style={{ fontSize: 11.5, color: 'var(--p-text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Keshlangan</div>
          <div style={{ fontSize: 16, fontWeight: 800, marginTop: 4 }}>Ali Karimov · 92% davomat</div>
          <div style={{ fontSize: 12, color: 'var(--p-text-muted)', fontWeight: 500, marginTop: 2 }}>To'liq ma'lumot uchun internet kerak</div>
        </PCard>
        <PCard padding={16} style={{ opacity: 0.85, display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ width: 36, height: 36, borderRadius: 10, background: 'var(--p-bg-soft)', color: 'var(--p-text-muted)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
            <span className="material-symbols-rounded" style={{ fontSize: 20 }}>sync_problem</span>
          </span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 700 }}>Yangi to'lovlar</div>
            <div style={{ fontSize: 11.5, color: 'var(--p-text-muted)', fontWeight: 600 }}>Internet aloqasi tiklanganda yuklanadi</div>
          </div>
        </PCard>
      </div>
    </div>
  );
}

Object.assign(window, {
  StudentDashboard, StudentPayments,
  NOTIFS, NotificationsScreen, NotificationDetailSheet, StudentAccount,
  LoadingState, EmptyState, ErrorState, OfflineState,
});
