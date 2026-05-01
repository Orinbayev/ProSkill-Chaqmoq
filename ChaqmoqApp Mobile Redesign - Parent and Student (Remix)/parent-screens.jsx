// ============================================================
// ChaqmoqApp — Parent screens (light, soft blue)
// ============================================================

// ---- 01 Login ----
function LoginScreen({ onSubmit }) {
  const [identifier, setIdentifier] = useState('+998 90 123 45 67');
  const [password, setPassword] = useState('••••••••');
  const [show, setShow] = useState(false);
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState(false);
  const [focus, setFocus] = useState(null);

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--p-bg)', color: 'var(--p-text)' }}>
      <StatusBar />
      <div style={{
        flex: 1, padding: '12px 24px 28px',
        display: 'flex', flexDirection: 'column',
        overflowY: 'auto',
      }} className="no-scrollbar">

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', marginTop: 20, marginBottom: 28 }}>
          <div style={{
            width: 72, height: 72, borderRadius: 22,
            background: 'linear-gradient(135deg, var(--p-primary), var(--p-primary-deep))',
            color: '#fff',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 18px 36px rgba(59,130,246,0.34)',
            marginBottom: 18,
          }}>
            <span className="material-symbols-rounded msr-fill" style={{ fontSize: 42 }}>bolt</span>
          </div>
          <h1 style={{ margin: 0, fontSize: 26, fontWeight: 800, letterSpacing: '-0.02em' }}>ChaqmoqApp</h1>
          <p style={{ margin: '8px 0 0', fontSize: 13.5, color: 'var(--p-text-soft)', maxWidth: 280, lineHeight: 1.5 }}>
            Ta'lim markazi va ota-ona o'rtasidagi ishonchli ko'prik
          </p>
        </div>

        {error && (
          <div style={{
            padding: '12px 14px', borderRadius: 14,
            background: 'var(--p-danger-bg)',
            border: '1px solid #FECACA',
            color: '#991B1B',
            display: 'flex', alignItems: 'center', gap: 10,
            fontSize: 12.5, fontWeight: 600,
            marginBottom: 14,
          }}>
            <span className="material-symbols-rounded" style={{ fontSize: 20, color: 'var(--p-danger)' }}>error</span>
            Login yoki parol noto'g'ri. Qaytadan urinib ko'ring.
          </div>
        )}

        {/* Identifier */}
        <div style={{
          background: 'var(--p-card)',
          border: `1.5px solid ${focus === 'id' ? 'var(--p-primary)' : 'var(--p-line)'}`,
          borderRadius: 16,
          padding: '12px 16px',
          display: 'flex', gap: 12, alignItems: 'center',
          marginBottom: 12,
          boxShadow: focus === 'id' ? '0 0 0 4px rgba(59,130,246,0.10)' : 'none',
          transition: 'all 0.18s',
        }}>
          <span className="material-symbols-rounded" style={{ fontSize: 22, color: focus === 'id' ? 'var(--p-primary)' : 'var(--p-text-muted)' }}>person</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, color: 'var(--p-text-muted)', fontWeight: 600 }}>Email yoki telefon</div>
            <input
              value={identifier}
              onChange={e => setIdentifier(e.target.value)}
              onFocus={() => setFocus('id')}
              onBlur={() => setFocus(null)}
              style={{ width: '100%', border: 0, outline: 'none', background: 'transparent', fontSize: 14.5, fontWeight: 600, color: 'var(--p-text)', fontFamily: 'inherit', padding: '2px 0 0' }}
            />
          </div>
        </div>

        {/* Password */}
        <div style={{
          background: 'var(--p-card)',
          border: `1.5px solid ${focus === 'pw' ? 'var(--p-primary)' : 'var(--p-line)'}`,
          borderRadius: 16,
          padding: '12px 16px',
          display: 'flex', gap: 12, alignItems: 'center',
          marginBottom: 14,
          boxShadow: focus === 'pw' ? '0 0 0 4px rgba(59,130,246,0.10)' : 'none',
          transition: 'all 0.18s',
        }}>
          <span className="material-symbols-rounded" style={{ fontSize: 22, color: focus === 'pw' ? 'var(--p-primary)' : 'var(--p-text-muted)' }}>lock</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, color: 'var(--p-text-muted)', fontWeight: 600 }}>Parol</div>
            <input
              type={show ? 'text' : 'password'}
              value={password}
              onChange={e => setPassword(e.target.value)}
              onFocus={() => setFocus('pw')}
              onBlur={() => setFocus(null)}
              style={{ width: '100%', border: 0, outline: 'none', background: 'transparent', fontSize: 14.5, fontWeight: 600, color: 'var(--p-text)', fontFamily: 'inherit', padding: '2px 0 0', letterSpacing: show ? 'normal' : '2px' }}
            />
          </div>
          <button onClick={() => setShow(s => !s)} style={{ border: 0, background: 'transparent', color: 'var(--p-text-muted)', cursor: 'pointer', padding: 0 }}>
            <span className="material-symbols-rounded" style={{ fontSize: 22 }}>{show ? 'visibility_off' : 'visibility'}</span>
          </button>
        </div>

        {/* Remember + forgot */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 22 }}>
          <button onClick={() => setRemember(r => !r)} style={{ display: 'inline-flex', alignItems: 'center', gap: 8, border: 0, background: 'transparent', cursor: 'pointer', color: 'var(--p-text)', fontFamily: 'inherit' }}>
            <span style={{
              width: 20, height: 20, borderRadius: 6,
              background: remember ? 'var(--p-primary)' : 'transparent',
              border: `1.5px solid ${remember ? 'var(--p-primary)' : 'var(--p-line-strong)'}`,
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              transition: 'all 0.15s',
            }}>
              {remember && <span className="material-symbols-rounded" style={{ fontSize: 14, color: '#fff' }}>check</span>}
            </span>
            <span style={{ fontSize: 13, fontWeight: 600 }}>Eslab qolish</span>
          </button>
          <a href="#" onClick={e => e.preventDefault()} style={{ fontSize: 13, fontWeight: 700, color: 'var(--p-primary)', textDecoration: 'none' }}>Parolni unutdingizmi?</a>
        </div>

        <PButton icon="login" onClick={() => onSubmit && onSubmit()}>Kirish</PButton>

        <div style={{
          marginTop: 16, padding: '12px 14px',
          borderRadius: 14,
          background: 'var(--p-success-bg)',
          border: '1px solid var(--p-success-line)',
          display: 'flex', alignItems: 'flex-start', gap: 10,
        }}>
          <span className="material-symbols-rounded" style={{ fontSize: 20, color: 'var(--p-success)', flexShrink: 0 }}>verified_user</span>
          <span style={{ fontSize: 12, color: '#065F46', lineHeight: 1.45, fontWeight: 500 }}>
            Kirish ma'lumotlari himoyalangan kanal orqali yuboriladi.
          </span>
        </div>

        <div style={{ marginTop: 'auto', textAlign: 'center', paddingTop: 24, fontSize: 12, color: 'var(--p-text-muted)' }}>
          Hisobingiz yo'qmi? <a href="#" onClick={e => e.preventDefault()} style={{ color: 'var(--p-primary)', fontWeight: 700, textDecoration: 'none' }}>Markaz bilan bog'laning</a>
        </div>
      </div>
    </div>
  );
}

// ---- 02 Parent Dashboard ----
const KIDS = [
  { id: 'ali', name: 'Ali Karimov', group: 'IELTS Academic · A1', age: 14, color: 'blue', attendance: 92, score: 4.7, debt: 0, nextLesson: 'Bugun, 15:00' },
  { id: 'madina', name: 'Madina Karimova', group: "Python boshlang'ich · B2", age: 12, color: 'amber', attendance: 87, score: 4.4, debt: 850000, nextLesson: 'Ertaga, 17:30' },
  { id: 'sardor', name: 'Sardor Karimov', group: "Matematika · 5-sinf", age: 10, color: 'teal', attendance: 78, score: 4.1, debt: 1250000, nextLesson: 'Dushanba, 14:00' },
];

function fmtSom(n) {
  if (n === 0) return "0 so'm";
  return n.toLocaleString('ru-RU').replace(/,/g, ' ') + " so'm";
}
function fmtSomShort(n) {
  if (n === 0) return '0';
  if (n >= 1000000) return (n / 1000000).toFixed(n % 1000000 === 0 ? 0 : 1) + ' mln';
  return (n / 1000).toFixed(0) + ' K';
}

function ParentDashboard({ activeKidId = 'ali', onOpenSelector, onOpenScreen }) {
  const kid = KIDS.find(k => k.id === activeKidId) || KIDS[0];
  const progressData = [3.8, 4.0, 3.9, 4.2, 4.4, 4.5, 4.4, 4.6, 4.7];

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
      <StatusBar />
      {/* Header */}
      <div style={{ padding: '8px 18px 12px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <button style={iconBtnLight}>
          <span className="material-symbols-rounded" style={{ fontSize: 22 }}>menu</span>
        </button>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 11.5, color: 'var(--p-text-muted)', fontWeight: 600 }}>Assalomu alaykum,</div>
          <div style={{ fontSize: 16, fontWeight: 800, letterSpacing: '-0.01em' }}>Dilshod aka 👋</div>
        </div>
        <button style={{ ...iconBtnLight, position: 'relative' }}>
          <span className="material-symbols-rounded" style={{ fontSize: 22 }}>notifications</span>
          <span style={{
            position: 'absolute', top: 7, right: 7,
            minWidth: 16, height: 16, borderRadius: 100,
            background: 'var(--p-danger)', color: '#fff',
            fontSize: 9.5, fontWeight: 800,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            padding: '0 4px',
            border: '2px solid var(--p-bg)',
          }}>3</span>
        </button>
        <Avatar name="Dilshod Karimov" size={40} color="slate" />
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 18px 100px' }} className="no-scrollbar">

        {/* Selected child card */}
        <div onClick={onOpenSelector} style={{
          background: 'linear-gradient(135deg, #3B82F6 0%, #2563EB 60%, #1E40AF 100%)',
          borderRadius: 22,
          padding: 18,
          color: '#fff',
          position: 'relative',
          overflow: 'hidden',
          boxShadow: '0 14px 30px rgba(37,99,235,0.32)',
          cursor: 'pointer',
          marginBottom: 14,
        }}>
          {/* decorative blob */}
          <div style={{ position: 'absolute', top: -40, right: -30, width: 160, height: 160, borderRadius: '50%', background: 'rgba(255,255,255,0.1)' }} />
          <div style={{ position: 'absolute', bottom: -50, right: 40, width: 100, height: 100, borderRadius: '50%', background: 'rgba(255,255,255,0.06)' }} />

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', position: 'relative', zIndex: 1 }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', opacity: 0.85 }}>Tanlangan farzand</div>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, fontWeight: 700, opacity: 0.95 }}>
              Almashtirish <span className="material-symbols-rounded" style={{ fontSize: 16 }}>swap_horiz</span>
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginTop: 14, position: 'relative', zIndex: 1 }}>
            <div style={{
              width: 56, height: 56, borderRadius: '50%',
              background: 'rgba(255,255,255,0.2)',
              border: '2px solid rgba(255,255,255,0.4)',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 20, fontWeight: 800,
            }}>{kid.name.split(' ').map(s => s[0]).join('').slice(0, 2)}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 19, fontWeight: 800, letterSpacing: '-0.01em' }}>{kid.name}</div>
              <div style={{ fontSize: 12.5, opacity: 0.9, fontWeight: 500, marginTop: 2 }}>{kid.group}</div>
            </div>
          </div>

          <div style={{
            marginTop: 14, padding: '10px 12px',
            background: 'rgba(255,255,255,0.14)',
            borderRadius: 14,
            display: 'flex', alignItems: 'center', gap: 10,
            position: 'relative', zIndex: 1,
            backdropFilter: 'blur(6px)',
          }}>
            <span className="material-symbols-rounded" style={{ fontSize: 18, opacity: 0.9 }}>schedule</span>
            <span style={{ fontSize: 12.5, fontWeight: 600 }}>Keyingi dars: {kid.nextLesson}</span>
          </div>
        </div>

        {/* Stats grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
          <StatCard
            icon="fact_check" iconBg="var(--p-success-bg)" iconFg="var(--p-success)"
            label="Davomat"
            value={`${kid.attendance}%`}
            sub="Bu oy"
            trend="up"
            onClick={() => onOpenScreen && onOpenScreen('attend')}
          />
          <StatCard
            icon="account_balance_wallet" iconBg="var(--p-danger-bg)" iconFg="var(--p-danger)"
            label="Qarzdorlik"
            value={kid.debt === 0 ? "0 so'm" : fmtSomShort(kid.debt) + " so'm"}
            sub={kid.debt === 0 ? "To'liq to'langan" : "Muddati o'tgan"}
            onClick={() => onOpenScreen && onOpenScreen('pay')}
          />
          <StatCard
            icon="grade" iconBg="var(--p-amber-bg)" iconFg="var(--p-amber-deep)"
            label="O'rtacha ball"
            value={kid.score.toFixed(1)}
            sub="5 dan"
            trend="up"
            onClick={() => onOpenScreen && onOpenScreen('progress')}
          />
          <StatCard
            icon="event" iconBg="var(--p-info-bg)" iconFg="var(--p-primary-deep)"
            label="Keyingi to'lov"
            value="15-may"
            sub="850 000 so'm"
          />
        </div>

        {/* Progress chart card */}
        <PCard padding={16} style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
            <div>
              <div style={{ fontSize: 12, color: 'var(--p-text-muted)', fontWeight: 600 }}>Bilim darajasi</div>
              <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.02em', marginTop: 2 }}>4.7 <span style={{ fontSize: 13, color: 'var(--p-text-muted)', fontWeight: 600 }}>/ 5</span></div>
            </div>
            <Badge tone="success">
              <span className="material-symbols-rounded" style={{ fontSize: 14 }}>trending_up</span>
              +0.3 oy ichida
            </Badge>
          </div>
          <div style={{ marginTop: 6 }}>
            <MiniLine data={progressData} color="#3B82F6" width={320} height={70} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10.5, color: 'var(--p-text-muted)', fontWeight: 600, marginTop: 4 }}>
            <span>Yan</span><span>Fev</span><span>Mar</span><span>Apr</span><span>May</span>
          </div>
        </PCard>

        {/* Quick actions */}
        <div style={{ fontSize: 14, fontWeight: 800, marginBottom: 10, letterSpacing: '-0.01em' }}>Tezkor amallar</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 8 }}>
          {[
            { icon: 'fact_check', label: 'Davomat', tone: 'success', id: 'attend' },
            { icon: 'payments',   label: "To'lov",  tone: 'info', id: 'pay' },
            { icon: 'insights',   label: 'Progress', tone: 'amber', id: 'progress' },
            { icon: 'forum',      label: 'Xabar',    tone: 'violet', id: 'msg' },
          ].map(qa => {
            const tones = {
              success: { bg: 'var(--p-success-bg)', fg: 'var(--p-success)' },
              info: { bg: 'var(--p-info-bg)', fg: 'var(--p-primary-deep)' },
              amber: { bg: 'var(--p-amber-bg)', fg: 'var(--p-amber-deep)' },
              violet: { bg: 'var(--p-violet-bg)', fg: 'var(--p-violet)' },
            };
            const t = tones[qa.tone];
            return (
              <button key={qa.label} onClick={() => onOpenScreen && onOpenScreen(qa.id)} style={{
                background: 'var(--p-card)',
                border: '1px solid var(--p-line)',
                borderRadius: 16,
                padding: '12px 6px',
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}>
                <span style={{
                  width: 36, height: 36, borderRadius: 12, background: t.bg, color: t.fg,
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <span className="material-symbols-rounded" style={{ fontSize: 20 }}>{qa.icon}</span>
                </span>
                <span style={{ fontSize: 11.5, fontWeight: 700 }}>{qa.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      <ParentBottomNav active="home" onChange={(id) => onOpenScreen && onOpenScreen(id)} />
    </div>
  );
}

function StatCard({ icon, iconBg, iconFg, label, value, sub, trend, onClick }) {
  return (
    <div onClick={onClick} style={{
      background: 'var(--p-card)',
      border: '1px solid var(--p-line)',
      borderRadius: 18,
      padding: 14,
      display: 'flex', flexDirection: 'column', gap: 4,
      cursor: onClick ? 'pointer' : 'default',
      boxShadow: 'var(--p-shadow-sm)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{
          width: 32, height: 32, borderRadius: 10, background: iconBg, color: iconFg,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <span className="material-symbols-rounded" style={{ fontSize: 18 }}>{icon}</span>
        </span>
        {trend === 'up' && <span className="material-symbols-rounded" style={{ fontSize: 16, color: 'var(--p-success)' }}>trending_up</span>}
        {trend === 'down' && <span className="material-symbols-rounded" style={{ fontSize: 16, color: 'var(--p-danger)' }}>trending_down</span>}
      </div>
      <div style={{ fontSize: 11.5, color: 'var(--p-text-muted)', fontWeight: 600, marginTop: 6 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.02em' }}>{value}</div>
      <div style={{ fontSize: 10.5, color: 'var(--p-text-muted)', fontWeight: 600 }}>{sub}</div>
    </div>
  );
}

// ---- 03 Parent Child Selector (bottom sheet) ----
function ChildSelectorSheet({ activeKidId, onPick, onClose, onAddChild }) {
  return (
    <BottomSheet title="Farzandni tanlang" onClose={onClose}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {KIDS.map(k => {
          const active = k.id === activeKidId;
          return (
            <button key={k.id} onClick={() => onPick(k.id)} style={{
              display: 'flex', alignItems: 'center', gap: 14,
              padding: '12px 14px',
              background: active ? 'var(--p-primary-tint)' : 'var(--p-card)',
              border: `1.5px solid ${active ? 'var(--p-primary)' : 'var(--p-line)'}`,
              borderRadius: 16,
              cursor: 'pointer',
              fontFamily: 'inherit',
              textAlign: 'left',
            }}>
              <Avatar name={k.name} size={44} color={k.color} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 800, color: 'var(--p-text)' }}>{k.name}</div>
                <div style={{ fontSize: 11.5, color: 'var(--p-text-muted)', fontWeight: 500, marginTop: 2 }}>{k.group}</div>
              </div>
              {active && (
                <span style={{
                  width: 24, height: 24, borderRadius: '50%',
                  background: 'var(--p-primary)', color: '#fff',
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <span className="material-symbols-rounded" style={{ fontSize: 16 }}>check</span>
                </span>
              )}
            </button>
          );
        })}
        <button onClick={onAddChild} style={{
          marginTop: 4,
          padding: '14px',
          border: '1.5px dashed var(--p-line-strong)',
          borderRadius: 16,
          background: 'transparent',
          color: 'var(--p-primary)',
          fontWeight: 700, fontSize: 13.5,
          fontFamily: 'inherit',
          cursor: 'pointer',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        }}>
          <span className="material-symbols-rounded" style={{ fontSize: 20 }}>add</span>
          Yangi farzand qo'shish
        </button>
      </div>
    </BottomSheet>
  );
}

// ---- 04 Parent Attendance ----
function AttendanceScreen({ onBack }) {
  const [selectedDay, setSelectedDay] = useState(15);
  // Build calendar (May 2026)
  const days = Array.from({ length: 31 }, (_, i) => i + 1);
  // attendance map: 1=present, 2=absent, 3=late
  const status = { 2:1, 3:1, 5:1, 6:1, 8:2, 9:1, 10:1, 12:1, 13:3, 15:1, 16:1, 17:1, 19:1, 20:2, 22:1, 23:1, 24:1 };

  const dayColor = (s) => s === 1 ? 'var(--p-success)' : s === 2 ? 'var(--p-danger)' : s === 3 ? 'var(--p-amber)' : null;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <StatusBar />
      <ParentAppBar
        title="Davomat"
        onBack={onBack}
        right={<button style={iconBtnLight}>
          <span className="material-symbols-rounded" style={{ fontSize: 22 }}>tune</span>
        </button>}
      />
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 18px 100px' }} className="no-scrollbar">

        {/* Summary */}
        <div style={{
          background: 'linear-gradient(135deg, #10B981, #059669)',
          color: '#fff',
          borderRadius: 20,
          padding: 18,
          display: 'flex', alignItems: 'center', gap: 16,
          marginBottom: 16,
          boxShadow: '0 12px 28px rgba(16,185,129,0.28)',
        }}>
          <div style={{ position: 'relative', width: 64, height: 64 }}>
            <svg viewBox="0 0 64 64" width="64" height="64">
              <circle cx="32" cy="32" r="26" fill="none" stroke="rgba(255,255,255,0.22)" strokeWidth="6" />
              <circle cx="32" cy="32" r="26" fill="none" stroke="#fff" strokeWidth="6"
                strokeDasharray="163.36" strokeDashoffset={163.36 - 163.36 * 0.92}
                strokeLinecap="round" transform="rotate(-90 32 32)" />
            </svg>
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, fontWeight: 800 }}>92%</div>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', opacity: 0.9 }}>May 2026</div>
            <div style={{ fontSize: 16, fontWeight: 800, marginTop: 2 }}>Ali Karimov</div>
            <div style={{ fontSize: 12, opacity: 0.9, marginTop: 2 }}>22 dan 20 dars qatnashgan</div>
          </div>
        </div>

        {/* Month nav */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <button style={{ ...iconBtnLight, width: 36, height: 36 }}>
            <span className="material-symbols-rounded" style={{ fontSize: 18 }}>chevron_left</span>
          </button>
          <div style={{ fontSize: 15, fontWeight: 800 }}>May 2026</div>
          <button style={{ ...iconBtnLight, width: 36, height: 36 }}>
            <span className="material-symbols-rounded" style={{ fontSize: 18 }}>chevron_right</span>
          </button>
        </div>

        {/* Calendar */}
        <PCard padding={14} style={{ marginBottom: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4, marginBottom: 6 }}>
            {['D','S','C','P','J','S','Y'].map((d, i) => (
              <div key={i} style={{ fontSize: 10.5, color: 'var(--p-text-muted)', fontWeight: 700, textAlign: 'center', padding: '4px 0' }}>{d}</div>
            ))}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4 }}>
            {/* May 1 2026 = Friday → 4 empty cells (D=0, S=1, C=2, P=3) */}
            {[0,1,2,3].map(i => <div key={'e'+i} />)}
            {days.map(d => {
              const s = status[d];
              const isSel = d === selectedDay;
              return (
                <button key={d} onClick={() => setSelectedDay(d)} style={{
                  height: 38, borderRadius: 12,
                  background: isSel ? 'var(--p-primary)' : 'transparent',
                  color: isSel ? '#fff' : 'var(--p-text)',
                  border: 0,
                  position: 'relative',
                  fontFamily: 'inherit',
                  fontSize: 12.5, fontWeight: 700,
                  cursor: 'pointer',
                }}>
                  {d}
                  {s && <span style={{
                    position: 'absolute', bottom: 4, left: '50%', transform: 'translateX(-50%)',
                    width: 5, height: 5, borderRadius: '50%',
                    background: isSel ? '#fff' : dayColor(s),
                  }} />}
                </button>
              );
            })}
          </div>
          <div style={{ display: 'flex', gap: 14, marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--p-line)', flexWrap: 'wrap' }}>
            {[
              { c: 'var(--p-success)', l: 'Kelgan' },
              { c: 'var(--p-danger)',  l: 'Kelmagan' },
              { c: 'var(--p-amber)',   l: 'Kechikkan' },
            ].map(x => (
              <span key={x.l} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--p-text-soft)', fontWeight: 600 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: x.c }} />{x.l}
              </span>
            ))}
          </div>
        </PCard>

        {/* Day detail */}
        <div style={{ fontSize: 14, fontWeight: 800, marginBottom: 8, letterSpacing: '-0.01em' }}>15-may, payshanba</div>
        {[
          { time: '09:00 — 10:30', subj: 'IELTS Reading', teacher: 'Aziz domla', status: 'present' },
          { time: '11:00 — 12:30', subj: 'IELTS Listening', teacher: 'Madina opa', status: 'present' },
          { time: '15:00 — 16:30', subj: 'IELTS Speaking', teacher: 'Aziz domla', status: 'late' },
        ].map((l, i) => (
          <PCard key={i} padding={12} style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 4, alignSelf: 'stretch',
              background: l.status === 'present' ? 'var(--p-success)' : l.status === 'late' ? 'var(--p-amber)' : 'var(--p-danger)',
              borderRadius: 4,
            }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 800 }}>{l.subj}</div>
              <div style={{ fontSize: 11.5, color: 'var(--p-text-muted)', fontWeight: 600, marginTop: 2 }}>{l.time} · {l.teacher}</div>
            </div>
            <Badge tone={l.status === 'present' ? 'success' : l.status === 'late' ? 'warning' : 'danger'}>
              {l.status === 'present' ? 'Kelgan' : l.status === 'late' ? 'Kechikkan' : 'Kelmagan'}
            </Badge>
          </PCard>
        ))}
      </div>
      <ParentBottomNav active="attend" />
    </div>
  );
}

// ---- 05 Parent Payments ----
const PAYMENTS = [
  { id: 1, month: 'May 2026', amount: 850000, status: 'pending', due: '15-may', child: 'Ali' },
  { id: 2, month: 'Apr 2026', amount: 850000, status: 'paid', date: '12-apr', method: 'Click', child: 'Ali' },
  { id: 3, month: 'Mar 2026', amount: 850000, status: 'paid', date: '14-mar', method: 'Payme', child: 'Ali' },
  { id: 4, month: 'Apr 2026', amount: 1250000, status: 'overdue', due: '20-apr', child: 'Sardor' },
  { id: 5, month: 'Fev 2026', amount: 850000, status: 'paid', date: '10-fev', method: 'Click', child: 'Ali' },
  { id: 6, month: 'Yan 2026', amount: 850000, status: 'paid', date: '08-yan', method: 'Naqd', child: 'Ali' },
];

function PaymentsScreen({ onBack, onOpenReminder }) {
  const [filter, setFilter] = useState('all');
  const filtered = PAYMENTS.filter(p =>
    filter === 'all' ? true :
    filter === 'paid' ? p.status === 'paid' :
    p.status !== 'paid'
  );
  const totalPaid = PAYMENTS.filter(p => p.status === 'paid').reduce((a, b) => a + b.amount, 0);
  const debt = PAYMENTS.filter(p => p.status !== 'paid').reduce((a, b) => a + b.amount, 0);

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <StatusBar />
      <ParentAppBar
        title="To'lovlar"
        onBack={onBack}
        right={<button onClick={onOpenReminder} style={iconBtnLight}>
          <span className="material-symbols-rounded" style={{ fontSize: 22 }}>notifications_active</span>
        </button>}
      />
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 18px 100px' }} className="no-scrollbar">

        {/* Hero summary */}
        <div style={{
          background: 'linear-gradient(135deg, #1E40AF 0%, #3B82F6 100%)',
          color: '#fff',
          borderRadius: 22,
          padding: 18,
          marginBottom: 14,
          position: 'relative', overflow: 'hidden',
          boxShadow: '0 14px 32px rgba(30,64,175,0.28)',
        }}>
          <div style={{ position: 'absolute', top: -50, right: -50, width: 180, height: 180, borderRadius: '50%', background: 'rgba(255,255,255,0.08)' }} />
          <div style={{ fontSize: 11.5, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', opacity: 0.85 }}>Joriy qarzdorlik</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 4 }}>
            <span style={{ fontSize: 30, fontWeight: 800, letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums' }}>1 250 000</span>
            <span style={{ fontSize: 14, opacity: 0.85, fontWeight: 600 }}>so'm</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6, fontSize: 12, opacity: 0.95 }}>
            <span className="material-symbols-rounded" style={{ fontSize: 16 }}>event</span>
            Keyingi to'lov: 15-may
          </div>

          <div style={{
            marginTop: 14, padding: '10px 12px',
            background: 'rgba(255,255,255,0.14)',
            borderRadius: 14,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            backdropFilter: 'blur(8px)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className="material-symbols-rounded msr-fill" style={{ fontSize: 22 }}>credit_card</span>
              <span style={{ fontSize: 13, fontWeight: 700 }}>Hozir to'lash</span>
            </div>
            <span className="material-symbols-rounded" style={{ fontSize: 20 }}>chevron_right</span>
          </div>
        </div>

        {/* Mini stats */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 14 }}>
          {[
            { l: 'Jami to\'langan', v: fmtSomShort(totalPaid), c: 'var(--p-success)' },
            { l: 'Bu oy', v: '0', c: 'var(--p-primary)' },
            { l: 'Qarzdorlik', v: fmtSomShort(debt), c: 'var(--p-danger)' },
          ].map((s, i) => (
            <PCard key={i} padding={12}>
              <div style={{ fontSize: 10.5, color: 'var(--p-text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{s.l}</div>
              <div style={{ fontSize: 16, fontWeight: 800, color: s.c, marginTop: 4, letterSpacing: '-0.02em' }}>{s.v}</div>
            </PCard>
          ))}
        </div>

        {/* Filter chips */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          {[
            { id: 'all', l: 'Barchasi', n: PAYMENTS.length },
            { id: 'paid', l: "To'langan", n: PAYMENTS.filter(p => p.status === 'paid').length },
            { id: 'debt', l: 'Qarzlar', n: PAYMENTS.filter(p => p.status !== 'paid').length },
          ].map(c => (
            <button key={c.id} onClick={() => setFilter(c.id)} style={{
              padding: '8px 14px', borderRadius: 100,
              background: filter === c.id ? 'var(--p-primary)' : 'var(--p-card)',
              color: filter === c.id ? '#fff' : 'var(--p-text-soft)',
              border: filter === c.id ? 0 : '1px solid var(--p-line)',
              fontFamily: 'inherit', fontWeight: 700, fontSize: 12,
              cursor: 'pointer',
              display: 'inline-flex', alignItems: 'center', gap: 6,
            }}>
              {c.l} <span style={{
                fontSize: 10, padding: '1px 6px', borderRadius: 100,
                background: filter === c.id ? 'rgba(255,255,255,0.2)' : 'var(--p-bg-soft)',
                color: filter === c.id ? '#fff' : 'var(--p-text-muted)',
              }}>{c.n}</span>
            </button>
          ))}
        </div>

        {/* List */}
        {filtered.map(p => (
          <PCard key={p.id} padding={14} style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 44, height: 44, borderRadius: 14,
              background: p.status === 'paid' ? 'var(--p-success-bg)' : p.status === 'overdue' ? 'var(--p-danger-bg)' : 'var(--p-amber-bg)',
              color: p.status === 'paid' ? 'var(--p-success)' : p.status === 'overdue' ? 'var(--p-danger)' : 'var(--p-amber-deep)',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <span className="material-symbols-rounded" style={{ fontSize: 22 }}>
                {p.status === 'paid' ? 'check_circle' : p.status === 'overdue' ? 'error' : 'schedule'}
              </span>
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13.5, fontWeight: 800 }}>{p.month}</div>
              <div style={{ fontSize: 11.5, color: 'var(--p-text-muted)', fontWeight: 600, marginTop: 2 }}>
                {p.child} · {p.status === 'paid' ? `${p.method} · ${p.date}` : `Muddat: ${p.due}`}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 14, fontWeight: 800, color: p.status === 'overdue' ? 'var(--p-danger)' : 'var(--p-text)', fontVariantNumeric: 'tabular-nums' }}>
                {fmtSomShort(p.amount)}
              </div>
              <div style={{ fontSize: 10, color: 'var(--p-text-muted)', fontWeight: 600 }}>so'm</div>
            </div>
          </PCard>
        ))}
      </div>
      <ParentBottomNav active="pay" />
    </div>
  );
}

// ---- 06 Payment Reminder Sheet ----
function PaymentReminderSheet({ onClose }) {
  const [picked, setPicked] = useState('3d');
  const opts = [
    { id: '1d', label: '1 kun oldin', sub: '14-may, 09:00' },
    { id: '3d', label: '3 kun oldin', sub: '12-may, 09:00' },
    { id: '7d', label: '7 kun oldin', sub: '8-may, 09:00' },
    { id: 'day', label: "To'lov kuni", sub: '15-may, 09:00' },
    { id: 'custom', label: 'Maxsus sana va vaqt', sub: 'Tanlang...' },
  ];
  return (
    <BottomSheet title="To'lov eslatmasi" onClose={onClose}>
      <div style={{ fontSize: 13, color: 'var(--p-text-soft)', marginBottom: 14, lineHeight: 1.5 }}>
        To'lov muddatidan oldin sizga eslatma yuboramiz.
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {opts.map(o => {
          const a = picked === o.id;
          return (
            <button key={o.id} onClick={() => setPicked(o.id)} style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '12px 14px',
              background: a ? 'var(--p-primary-tint)' : 'var(--p-card)',
              border: `1.5px solid ${a ? 'var(--p-primary)' : 'var(--p-line)'}`,
              borderRadius: 14,
              cursor: 'pointer', fontFamily: 'inherit',
              textAlign: 'left',
            }}>
              <span style={{
                width: 22, height: 22, borderRadius: '50%',
                border: `2px solid ${a ? 'var(--p-primary)' : 'var(--p-line-strong)'}`,
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                background: a ? 'var(--p-primary)' : '#fff',
                flexShrink: 0,
              }}>
                {a && <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#fff' }} />}
              </span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--p-text)' }}>{o.label}</div>
                <div style={{ fontSize: 11.5, color: 'var(--p-text-muted)', fontWeight: 600, marginTop: 2 }}>{o.sub}</div>
              </div>
              {o.id === 'custom' && (
                <span className="material-symbols-rounded" style={{ fontSize: 18, color: 'var(--p-text-muted)' }}>chevron_right</span>
              )}
            </button>
          );
        })}
      </div>
      <div style={{ marginTop: 16 }}>
        <PButton icon="check" onClick={onClose}>Saqlash</PButton>
      </div>
    </BottomSheet>
  );
}

Object.assign(window, {
  KIDS, fmtSom, fmtSomShort,
  LoginScreen, ParentDashboard, StatCard,
  ChildSelectorSheet, AttendanceScreen, PaymentsScreen, PaymentReminderSheet,
});
