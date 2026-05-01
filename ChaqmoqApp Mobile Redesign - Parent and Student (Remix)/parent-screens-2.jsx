// ============================================================
// ChaqmoqApp — Parent screens part 2 (Progress, Profile, Add Child)
// ============================================================

// ---- 07 Parent Progress ----
const SUBJECTS = [
  { id: 'reading', name: 'Reading', icon: 'menu_book', color: 'var(--p-primary)', bg: 'var(--p-info-bg)', score: 4.8, change: '+0.4', level: 'A2 → B1' },
  { id: 'listening', name: 'Listening', icon: 'headphones', color: 'var(--p-success)', bg: 'var(--p-success-bg)', score: 4.6, change: '+0.2', level: 'B1' },
  { id: 'writing', name: 'Writing', icon: 'edit_note', color: 'var(--p-amber-deep)', bg: 'var(--p-amber-bg)', score: 4.2, change: '+0.5', level: 'A2' },
  { id: 'speaking', name: 'Speaking', icon: 'record_voice_over', color: 'var(--p-violet)', bg: 'var(--p-violet-bg)', score: 4.5, change: '+0.3', level: 'B1' },
];

function ProgressScreen({ onBack, onOpenSubject }) {
  const [period, setPeriod] = useState('3m');
  const data = period === '1m' ? [4.3,4.4,4.5,4.6,4.7] : period === '3m' ? [4.1,4.2,4.3,4.4,4.5,4.6,4.6,4.7] : [3.6,3.8,3.9,4.0,4.1,4.2,4.3,4.5,4.6,4.7];

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <StatusBar />
      <ParentAppBar
        title="Progress"
        onBack={onBack}
        right={<button style={iconBtnLight}>
          <span className="material-symbols-rounded" style={{ fontSize: 22 }}>share</span>
        </button>}
      />
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 18px 100px' }} className="no-scrollbar">

        {/* Overall card */}
        <div style={{
          background: 'linear-gradient(135deg, #6C63FF 0%, #4F46E5 100%)',
          color: '#fff', borderRadius: 22, padding: 18, marginBottom: 14,
          boxShadow: '0 14px 30px rgba(108,99,255,0.30)',
          position: 'relative', overflow: 'hidden',
        }}>
          <div style={{ position: 'absolute', top: -40, right: -40, width: 160, height: 160, borderRadius: '50%', background: 'rgba(255,255,255,0.08)' }} />
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14, position: 'relative' }}>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', opacity: 0.85 }}>Umumiy progress</div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 6 }}>
                <span style={{ fontSize: 32, fontWeight: 800, letterSpacing: '-0.02em' }}>4.7</span>
                <span style={{ fontSize: 13, opacity: 0.85, fontWeight: 600 }}>/ 5</span>
              </div>
              <div style={{ fontSize: 12, fontWeight: 700, marginTop: 4, opacity: 0.95, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <span className="material-symbols-rounded" style={{ fontSize: 14 }}>trending_up</span>
                +0.3 oy ichida · IELTS 6.5 yo'lida
              </div>
            </div>
            <div style={{ position: 'relative', width: 78, height: 78 }}>
              <svg viewBox="0 0 78 78" width="78" height="78">
                <circle cx="39" cy="39" r="32" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="6" />
                <circle cx="39" cy="39" r="32" fill="none" stroke="#fff" strokeWidth="6"
                  strokeDasharray="201" strokeDashoffset={201 - 201 * 0.94}
                  strokeLinecap="round" transform="rotate(-90 39 39)" />
              </svg>
              <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 800 }}>94%</div>
            </div>
          </div>
          <MiniLine data={data} color="#fff" width={320} height={56} fill={false} />
        </div>

        {/* Period selector */}
        <div style={{ display: 'flex', gap: 6, padding: 4, background: 'var(--p-card)', border: '1px solid var(--p-line)', borderRadius: 100, marginBottom: 14 }}>
          {[{i:'1m',l:'1 oy'},{i:'3m',l:'3 oy'},{i:'1y',l:'1 yil'}].map(p => (
            <button key={p.i} onClick={() => setPeriod(p.i)} style={{
              flex: 1, padding: '7px 0', borderRadius: 100,
              background: period === p.i ? 'var(--p-primary)' : 'transparent',
              color: period === p.i ? '#fff' : 'var(--p-text-soft)',
              border: 0, fontFamily: 'inherit', fontSize: 12, fontWeight: 700, cursor: 'pointer',
            }}>{p.l}</button>
          ))}
        </div>

        {/* Subjects */}
        <div style={{ fontSize: 14, fontWeight: 800, marginBottom: 10 }}>Fanlar bo'yicha</div>
        {SUBJECTS.map(s => (
          <PCard key={s.id} padding={14} style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer' }} onClick={() => onOpenSubject && onOpenSubject(s)}>
            <span style={{
              width: 40, height: 40, borderRadius: 12,
              background: s.bg, color: s.color,
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <span className="material-symbols-rounded" style={{ fontSize: 22 }}>{s.icon}</span>
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <span style={{ fontSize: 13.5, fontWeight: 800 }}>{s.name}</span>
                <span style={{ fontSize: 13, fontWeight: 800, color: s.color, fontVariantNumeric: 'tabular-nums' }}>{s.score}</span>
              </div>
              <div style={{ marginTop: 6, height: 6, background: 'var(--p-bg-soft)', borderRadius: 100, overflow: 'hidden' }}>
                <div style={{ width: `${(s.score / 5) * 100}%`, height: '100%', background: s.color, borderRadius: 100, transition: 'width 0.6s ease' }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
                <span style={{ fontSize: 10.5, color: 'var(--p-text-muted)', fontWeight: 600 }}>{s.level}</span>
                <span style={{ fontSize: 10.5, color: 'var(--p-success)', fontWeight: 700 }}>{s.change}</span>
              </div>
            </div>
          </PCard>
        ))}

        {/* Teacher comment */}
        <div style={{ fontSize: 14, fontWeight: 800, margin: '14px 0 10px' }}>O'qituvchi izohi</div>
        <PCard padding={14} style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
          <Avatar name="Aziz Tursunov" size={40} color="violet" />
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 13, fontWeight: 800 }}>Aziz Tursunov</span>
              <span style={{ fontSize: 10.5, color: 'var(--p-text-muted)', fontWeight: 600 }}>3 kun oldin</span>
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--p-text-muted)', fontWeight: 600, marginBottom: 6 }}>IELTS Speaking · A1 guruh</div>
            <div style={{ fontSize: 12.5, color: 'var(--p-text-soft)', lineHeight: 1.5 }}>
              Ali bu hafta speaking qismida sezilarli o'sish ko'rsatdi. Pronunciation va fluency yaxshilanmoqda. Uyga vazifa: Cambridge 17, Test 2 — Part 2.
            </div>
          </div>
        </PCard>

        {/* Highlights */}
        <div style={{ fontSize: 14, fontWeight: 800, margin: '14px 0 10px' }}>Yutuqlar</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {[
            { icon: 'emoji_events', label: '5 hafta a\'lo', sub: 'Eng yaxshi guruhda', tone: 'amber' },
            { icon: 'local_fire_department', label: '12 kunlik streak', sub: 'Davomiy faollik', tone: 'danger' },
          ].map((h, i) => {
            const tones = { amber: ['var(--p-amber-bg)', 'var(--p-amber-deep)'], danger: ['var(--p-danger-bg)', 'var(--p-danger)'] };
            const [bg, fg] = tones[h.tone];
            return (
              <PCard key={i} padding={12} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <span style={{ width: 32, height: 32, borderRadius: 10, background: bg, color: fg, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span className="material-symbols-rounded msr-fill" style={{ fontSize: 18 }}>{h.icon}</span>
                </span>
                <div style={{ fontSize: 12.5, fontWeight: 800 }}>{h.label}</div>
                <div style={{ fontSize: 10.5, color: 'var(--p-text-muted)', fontWeight: 600 }}>{h.sub}</div>
              </PCard>
            );
          })}
        </div>
      </div>
      <ParentBottomNav active="progress" />
    </div>
  );
}

function SubjectDetailSheet({ subject, onClose }) {
  if (!subject) return null;
  const data = [3.8,4.0,4.1,4.2,4.3,4.5,4.6,subject.score];
  return (
    <BottomSheet title={subject.name} onClose={onClose} height="80%">
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14 }}>
        <span style={{ width: 56, height: 56, borderRadius: 16, background: subject.bg, color: subject.color, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
          <span className="material-symbols-rounded" style={{ fontSize: 30 }}>{subject.icon}</span>
        </span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-0.02em' }}>{subject.score} <span style={{ fontSize: 13, color: 'var(--p-text-muted)', fontWeight: 600 }}>/ 5</span></div>
          <div style={{ fontSize: 12, color: 'var(--p-text-muted)', fontWeight: 600 }}>{subject.level} · {subject.change} oy ichida</div>
        </div>
      </div>
      <PCard padding={14} style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 11.5, color: 'var(--p-text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>O'sish dinamikasi</div>
        <MiniLine data={data} color={subject.color} width={320} height={80} />
      </PCard>
      <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 8 }}>So'nggi natijalar</div>
      {[
        { d: '12-may', t: 'Mock test #4', s: '4.8' },
        { d: '5-may', t: 'Reading practice', s: '4.6' },
        { d: '28-apr', t: 'Mock test #3', s: '4.4' },
      ].map((r, i) => (
        <PCard key={i} padding={12} style={{ marginBottom: 6, display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ width: 36, height: 36, borderRadius: 10, background: 'var(--p-bg-soft)', color: subject.color, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
            <span className="material-symbols-rounded" style={{ fontSize: 18 }}>quiz</span>
          </span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 700 }}>{r.t}</div>
            <div style={{ fontSize: 11, color: 'var(--p-text-muted)', fontWeight: 600 }}>{r.d}</div>
          </div>
          <span style={{ fontSize: 14, fontWeight: 800, color: subject.color }}>{r.s}</span>
        </PCard>
      ))}
    </BottomSheet>
  );
}

// ---- 08 Parent Profile ----
function ProfileScreen({ onBack, onAddChild }) {
  const settings = [
    { i: 'edit', l: 'Profilni tahrirlash' },
    { i: 'lock', l: 'Xavfsizlik' },
    { i: 'notifications', l: 'Bildirishnomalar', val: 'Yoqilgan' },
    { i: 'language', l: 'Til', val: "O'zbek" },
    { i: 'dark_mode', l: 'Ko\'rinish', val: 'Yorug\'' },
    { i: 'help', l: 'Yordam va qo\'llab-quvvatlash' },
    { i: 'info', l: 'Ilova haqida', val: 'v2.4.1' },
  ];

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <StatusBar />
      <ParentAppBar title="Profil" />
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 18px 100px' }} className="no-scrollbar">

        {/* Parent card */}
        <PCard padding={18} style={{ marginBottom: 14, textAlign: 'center', position: 'relative' }}>
          <div style={{ display: 'inline-block', position: 'relative', marginBottom: 10 }}>
            <Avatar name="Dilshod Karimov" size={80} color="slate" />
            <button style={{
              position: 'absolute', right: -2, bottom: -2,
              width: 28, height: 28, borderRadius: '50%',
              background: 'var(--p-primary)', color: '#fff', border: '3px solid var(--p-card)',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
            }}>
              <span className="material-symbols-rounded" style={{ fontSize: 14 }}>photo_camera</span>
            </button>
          </div>
          <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.01em' }}>Dilshod Karimov</div>
          <div style={{ fontSize: 12, color: 'var(--p-text-muted)', fontWeight: 600, marginTop: 2 }}>Ota-ona</div>

          <div style={{ display: 'flex', justifyContent: 'center', gap: 10, marginTop: 14 }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--p-text-soft)', fontWeight: 600 }}>
              <span className="material-symbols-rounded" style={{ fontSize: 16, color: 'var(--p-primary)' }}>phone</span>
              +998 90 123 45 67
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 10, marginTop: 6 }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--p-text-soft)', fontWeight: 600 }}>
              <span className="material-symbols-rounded" style={{ fontSize: 16, color: 'var(--p-primary)' }}>mail</span>
              dilshod.k@example.uz
            </div>
          </div>
        </PCard>

        {/* My children */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <div style={{ fontSize: 14, fontWeight: 800 }}>Mening farzandlarim</div>
          <a href="#" onClick={e => e.preventDefault()} style={{ fontSize: 12, color: 'var(--p-primary)', fontWeight: 700, textDecoration: 'none' }}>Barchasi ›</a>
        </div>
        <div style={{ display: 'flex', gap: 10, overflowX: 'auto', paddingBottom: 4, marginBottom: 14, marginLeft: -18, paddingLeft: 18, paddingRight: 18 }} className="no-scrollbar">
          {KIDS.map(k => (
            <PCard key={k.id} padding={12} style={{ minWidth: 130, flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
              <Avatar name={k.name} size={48} color={k.color} />
              <div style={{ fontSize: 12.5, fontWeight: 800, textAlign: 'center' }}>{k.name.split(' ')[0]}</div>
              <div style={{ fontSize: 10.5, color: 'var(--p-text-muted)', fontWeight: 600, textAlign: 'center' }}>{k.age} yosh</div>
              <Badge tone="info">{k.attendance}% davomat</Badge>
            </PCard>
          ))}
          <button onClick={onAddChild} style={{
            minWidth: 130, flexShrink: 0,
            border: '1.5px dashed var(--p-line-strong)',
            borderRadius: 20, background: 'transparent',
            padding: 12,
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 6,
            color: 'var(--p-primary)', fontFamily: 'inherit', fontWeight: 700, fontSize: 12,
            cursor: 'pointer',
          }}>
            <span style={{ width: 48, height: 48, borderRadius: '50%', background: 'var(--p-primary-tint)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
              <span className="material-symbols-rounded" style={{ fontSize: 24 }}>add</span>
            </span>
            Qo'shish
          </button>
        </div>

        {/* Settings */}
        <div style={{ fontSize: 14, fontWeight: 800, marginBottom: 10 }}>Sozlamalar</div>
        <PCard padding={4}>
          {settings.map((s, i) => (
            <div key={s.i} style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '12px 12px',
              borderBottom: i < settings.length - 1 ? '1px solid var(--p-line)' : 'none',
              cursor: 'pointer',
            }}>
              <span style={{
                width: 34, height: 34, borderRadius: 10,
                background: 'var(--p-bg-soft)', color: 'var(--p-primary-deep)',
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <span className="material-symbols-rounded" style={{ fontSize: 18 }}>{s.i}</span>
              </span>
              <span style={{ flex: 1, fontSize: 13.5, fontWeight: 600 }}>{s.l}</span>
              {s.val && <span style={{ fontSize: 12, color: 'var(--p-text-muted)', fontWeight: 600 }}>{s.val}</span>}
              <span className="material-symbols-rounded" style={{ fontSize: 18, color: 'var(--p-text-muted)' }}>chevron_right</span>
            </div>
          ))}
        </PCard>

        {/* Logout */}
        <button style={{
          width: '100%', marginTop: 14,
          padding: 14, borderRadius: 16,
          background: 'var(--p-danger-bg)', color: 'var(--p-danger)',
          border: 0, fontFamily: 'inherit', fontWeight: 700, fontSize: 13.5,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          cursor: 'pointer',
        }}>
          <span className="material-symbols-rounded" style={{ fontSize: 20 }}>logout</span>
          Chiqish
        </button>
      </div>
      <ParentBottomNav active="profile" />
    </div>
  );
}

// ---- 09 Add Child ----
function AddChildScreen({ onBack }) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <StatusBar />
      <ParentAppBar title="Yangi farzand" onBack={onBack} />
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 18px 100px' }} className="no-scrollbar">

        <div style={{ textAlign: 'center', padding: '8px 0 22px' }}>
          <div style={{ display: 'inline-block', position: 'relative' }}>
            <div style={{
              width: 84, height: 84, borderRadius: '50%',
              background: 'var(--p-primary-tint)',
              border: '2px dashed var(--p-primary)',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--p-primary)',
            }}>
              <span className="material-symbols-rounded" style={{ fontSize: 36 }}>add_a_photo</span>
            </div>
          </div>
          <div style={{ fontSize: 12, color: 'var(--p-text-muted)', fontWeight: 600, marginTop: 8 }}>Rasm qo'shing (ixtiyoriy)</div>
        </div>

        {[
          { i: 'person', l: 'To\'liq ism', v: 'Madina Karimova' },
          { i: 'cake', l: 'Tug\'ilgan sana', v: '12.04.2014', chev: true },
          { i: 'wc', l: 'Jinsi', v: 'Qiz', chev: true },
          { i: 'school', l: 'Maktab', v: '24-maktab' },
          { i: 'class', l: 'Sinfi', v: '6-A', chev: true },
        ].map((f, i) => (
          <div key={i} style={{
            background: 'var(--p-card)',
            border: '1px solid var(--p-line)',
            borderRadius: 16, padding: '12px 16px',
            display: 'flex', gap: 12, alignItems: 'center',
            marginBottom: 10,
          }}>
            <span className="material-symbols-rounded" style={{ fontSize: 22, color: 'var(--p-text-muted)' }}>{f.i}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 11, color: 'var(--p-text-muted)', fontWeight: 600 }}>{f.l}</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--p-text)', marginTop: 2 }}>{f.v}</div>
            </div>
            {f.chev && <span className="material-symbols-rounded" style={{ fontSize: 18, color: 'var(--p-text-muted)' }}>chevron_right</span>}
          </div>
        ))}

        <div style={{ fontSize: 14, fontWeight: 800, margin: '8px 0 10px' }}>Markaz va guruh</div>
        {[
          { i: 'apartment', l: 'O\'quv markazi', v: 'ProSkill Academy' },
          { i: 'groups', l: 'Guruh', v: "Python boshlang'ich · B2", chev: true },
          { i: 'qr_code_2', l: 'Taklif kodi', v: 'PSK-MK-2026', chev: true },
        ].map((f, i) => (
          <div key={i} style={{
            background: 'var(--p-card)',
            border: '1px solid var(--p-line)',
            borderRadius: 16, padding: '12px 16px',
            display: 'flex', gap: 12, alignItems: 'center',
            marginBottom: 10,
          }}>
            <span className="material-symbols-rounded" style={{ fontSize: 22, color: 'var(--p-text-muted)' }}>{f.i}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 11, color: 'var(--p-text-muted)', fontWeight: 600 }}>{f.l}</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--p-text)', marginTop: 2 }}>{f.v}</div>
            </div>
            {f.chev && <span className="material-symbols-rounded" style={{ fontSize: 18, color: 'var(--p-text-muted)' }}>chevron_right</span>}
          </div>
        ))}

        <div style={{
          marginTop: 8, padding: '12px 14px',
          background: 'var(--p-info-bg)', border: '1px solid #BFDBFE',
          borderRadius: 14,
          display: 'flex', alignItems: 'flex-start', gap: 10,
        }}>
          <span className="material-symbols-rounded" style={{ fontSize: 20, color: 'var(--p-primary-deep)', flexShrink: 0 }}>info</span>
          <span style={{ fontSize: 12, color: '#1E40AF', fontWeight: 500, lineHeight: 1.45 }}>
            Markazingizdan olingan taklif kodini kiriting, biz farzandni guruhga avtomatik biriktiramiz.
          </span>
        </div>

        <div style={{ marginTop: 16 }}>
          <PButton icon="add">Farzandni qo'shish</PButton>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, {
  SUBJECTS, ProgressScreen, SubjectDetailSheet, ProfileScreen, AddChildScreen,
});
