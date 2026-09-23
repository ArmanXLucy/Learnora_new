import React, { useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowLeft,
  BookOpen,
  Check,
  ChevronRight,
  Code2,
  GraduationCap,
  LayoutDashboard,
  Menu,
  Play,
  Search,
  Sparkles,
  Trophy,
  Users,
  X,
  Bell,
  CalendarDays,
  CircleHelp,
  Flame,
  Award,
  ChartNoAxesColumnIncreasing,
  Clock3,
  MousePointer2,
  Workflow,
  CheckCircle2,
  Instagram,
  Twitter,
  Youtube,
  Mail,
  Phone,
  Lock,
  User,
  Eye,
  EyeOff,
  LogOut,
  Route,
  BadgeCheck,
  TerminalSquare,
  SlidersHorizontal
} from "lucide-react";

const courses = [
  { title: "Web Development", subtitle: "HTML, CSS & JavaScript", progress: 68, tone: "blue", icon: Code2, sketch: "code" },
  { title: "UI/UX Design", subtitle: "Design better experiences", progress: 42, tone: "purple", icon: Sparkles, sketch: "design" },
  { title: "Motion Design", subtitle: "Create beautiful animations", progress: 75, tone: "green", icon: Play, sketch: "motion" }
];

const tasks = [
  { title: "Complete React Basics", time: "08:00 PM", done: false },
  { title: "Build portfolio project", time: "04:00 PM", done: false },
  { title: "Read UI/UX article", time: "10:30 AM", done: false },
  { title: "Watch design tutorial", time: "Completed", done: true }
];

const capabilities = [
  {
    key: "paths",
    title: "Personalised learning paths",
    text: "Every course reshapes itself around what you already know and where you want to end up.",
    sketch: "map"
  },
  {
    key: "practice",
    title: "Real, hands-on practice",
    text: "Write code, design screens, and build projects in-browser instead of just watching lessons.",
    sketch: "terminal"
  },
  {
    key: "progress",
    title: "Live progress tracking",
    text: "A quiet dashboard keeps score of streaks, weekly effort, and skill growth as you go.",
    sketch: "chart"
  },
  {
    key: "certify",
    title: "Milestones that count",
    text: "Earn certificates and badges you can actually show an employer, not just a completion email.",
    sketch: "badge"
  }
];

function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [page, setPage] = useState("landing"); // landing | auth | dashboard
  const [authMode, setAuthMode] = useState("login");
  const [authLoading, setAuthLoading] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [taskState, setTaskState] = useState(tasks);
  const [displayName, setDisplayName] = useState("Alex Thompson");
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    if (page !== "landing") return;
    const elements = document.querySelectorAll(
      ".how-it-works, .capability-section, .content-section, .process-step, .capability-card, .large-course-card, .path-grid > div, .simple-banner, .pricing-card, .trusted-strip, .dashboard-preview"
    );

    elements.forEach((element) => element.classList.add("reveal-on-scroll"));

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );

    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [page]);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
  }, [page]);

  const scrollTo = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
    setMenuOpen(false);
  };

  const openAuth = (mode = "login") => {
    setAuthMode(mode);
    setPage("auth");
    setMenuOpen(false);
  };

  const backToHome = () => {
    setPage("landing");
  };

  // Returning to the landing page from the dashboard keeps the session —
  // the person only leaves the logged-in state via the explicit logout button.
  const goHome = () => {
    setPage("landing");
  };

  const goToDashboard = () => {
    setPage("dashboard");
  };

  const submitAuth = (event) => {
    event.preventDefault();
    if (!email.trim() || !password.trim()) return;
    if (authMode === "register" && !name.trim()) return;

    setAuthLoading(true);
    const finalName =
      authMode === "register" && name.trim()
        ? name.trim()
        : email.split("@")[0].replace(/[._]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

    window.setTimeout(() => {
      setDisplayName(finalName || "Alex Thompson");
      setAuthLoading(false);
      setLoggedIn(true);
      setPage("dashboard");
      setEmail("");
      setPassword("");
      setName("");
    }, 700);
  };

  const logout = () => {
    setLoggedIn(false);
    setPage("landing");
    setAuthMode("login");
  };

  const toggleTask = (index) => {
    setTaskState((current) =>
      current.map((task, i) =>
        i === index ? { ...task, done: !task.done } : task
      )
    );
  };

  const filteredCourses = courses.filter((course) =>
    `${course.title} ${course.subtitle}`
      .toLowerCase()
      .includes(searchTerm.toLowerCase())
  );

  if (page === "auth") {
    return (
      <AuthPage
        mode={authMode}
        setMode={setAuthMode}
        email={email}
        setEmail={setEmail}
        password={password}
        setPassword={setPassword}
        name={name}
        setName={setName}
        showPassword={showPassword}
        setShowPassword={setShowPassword}
        onSubmit={submitAuth}
        onBack={backToHome}
        loading={authLoading}
      />
    );
  }

  if (page === "dashboard") {
    return (
      <DashboardPage
        displayName={displayName}
        searchTerm={searchTerm}
        setSearchTerm={setSearchTerm}
        filteredCourses={filteredCourses}
        taskState={taskState}
        toggleTask={toggleTask}
        onLogout={logout}
        onHome={goHome}
      />
    );
  }

  return (
    <main className="app-shell">
      <header className="navbar">
        <button className="brand" onClick={() => scrollTo("home")}>
          <span className="brand-mark"><GraduationCap size={23} /></span>
          <span>Learnora</span>
        </button>

        <button
          className="mobile-menu"
          aria-label="Toggle navigation"
          onClick={() => setMenuOpen((value) => !value)}
        >
          {menuOpen ? <X /> : <Menu />}
        </button>

        <nav className={menuOpen ? "nav-links open" : "nav-links"}>
          <button onClick={() => scrollTo("courses")}>Courses</button>
          <button onClick={() => scrollTo("capabilities")}>Capabilities</button>
          <button onClick={() => scrollTo("paths")}>Learning Paths</button>
          <button onClick={() => scrollTo("instructors")}>Instructors</button>
          <button onClick={() => scrollTo("pricing")}>Pricing</button>
          {loggedIn ? (
            <button className="nav-cta" onClick={goToDashboard}>
              Dashboard <ArrowRight size={16} />
            </button>
          ) : (
            <button className="nav-cta" onClick={() => openAuth("login")}>
              Log in <ArrowRight size={16} />
            </button>
          )}
        </nav>
      </header>

      <section className="hero" id="home">
        <div className="ambient ambient-one" />
        <div className="ambient ambient-two" />
        <div className="ambient ambient-three" />
        <div className="ambient ambient-four" />
        <div className="ambient ambient-five" />

        <div className="learning-decoration book-decoration">
          <BookOpen size={36} />
        </div>
        <div className="learning-decoration code-decoration">
          <Code2 size={32} />
        </div>
        <div className="learning-decoration cap-decoration">
          <GraduationCap size={42} />
        </div>
        <div className="learning-decoration pencil-decoration">✎</div>
        <div className="learning-decoration spark-decoration-one">
          <Sparkles size={22} />
        </div>
        <div className="learning-decoration spark-decoration-two">
          <Sparkles size={16} />
        </div>
        <div className="learning-decoration dot-decoration-one" />
        <div className="learning-decoration dot-decoration-two" />
        <div className="learning-decoration dot-decoration-three" />
        <div className="learning-decoration ring-decoration" />
        <div className="progress-orbit orbit-one">75%</div>
        <div className="progress-orbit orbit-two">60%</div>

        <div className="hero-copy">
          <div className="eyebrow"><Sparkles size={15} /> Learn something new every day</div>
          <h1>Your Future Starts With <span>Learning</span></h1>
          <p>
            Build real skills through interactive courses, expert guidance,
            and learning paths designed for your goals.
          </p>
          <div className="hero-actions">
            <button className="primary-button" onClick={() => scrollTo("dashboard")}>
              Explore Courses <ArrowRight size={18} />
            </button>
            <button className="secondary-button" onClick={() => openAuth("register")}>
              <Play size={16} /> Watch Demo
            </button>
          </div>
        </div>

        <div className="dashboard-preview" id="dashboard">
          <aside className="dashboard-sidebar">
            <div className="mini-brand"><GraduationCap size={17} /> Learnora</div>
            <button className="side-item active"><LayoutDashboard size={15} /> Dashboard</button>
            <button className="side-item" onClick={() => scrollTo("courses")}><BookOpen size={15} /> My Courses</button>
            <button className="side-item" onClick={() => scrollTo("paths")}><Trophy size={15} /> Learning Paths</button>
            <button className="side-item" onClick={() => scrollTo("courses")}><Check size={15} /> Assignments</button>
            <button className="side-item"><ChartNoAxesColumnIncreasing size={15} /> Progress</button>
            <button className="side-item"><Bell size={15} /> Notifications</button>
          </aside>

          <div className="dashboard-main">
            <div className="dashboard-topbar">
              <div>
                <h3>Hello, Alex 👋</h3>
                <span>Let’s learn something new today!</span>
              </div>
              <div className="dashboard-search">
                <Search size={15} />
                <input
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="Search courses..."
                  aria-label="Search courses"
                />
              </div>
              <button className="icon-button" aria-label="Notifications"><Bell size={17} /></button>
            </div>

            <div className="course-heading">
              <h3>My Courses</h3>
              <button onClick={() => scrollTo("courses")}>View all <ChevronRight size={14} /></button>
            </div>

            <div className="course-grid">
              {filteredCourses.map((course) => {
                const Icon = course.icon;
                return (
                  <article className={`mini-course ${course.tone}`} key={course.title}>
                    <div className="course-icon"><Icon size={20} /></div>
                    <h4>{course.title}</h4>
                    <p>{course.subtitle}</p>
                    <div className="progress-line"><span style={{ width: `${course.progress}%` }} /></div>
                    <div className="course-meta"><span>{course.progress}% complete</span><ChevronRight size={14} /></div>
                  </article>
                );
              })}
              {filteredCourses.length === 0 && <p className="empty-state">No courses found.</p>}
            </div>

            <div className="analytics-grid">
              <div className="analytics-card">
                <div className="card-heading"><h4>Weekly Learning Progress</h4><span>+24%</span></div>
                <div className="bar-chart">
                  {[35, 52, 74, 46, 67, 56, 83].map((height, index) => (
                    <div className="bar-column" key={index}>
                      <span style={{ height: `${height}%` }} />
                      <small>{["M", "T", "W", "T", "F", "S", "S"][index]}</small>
                    </div>
                  ))}
                </div>
              </div>

              <div className="analytics-card performance-card">
                <div className="card-heading"><h4>Your Performance</h4><Trophy size={16} /></div>
                <div className="score-ring"><strong>92%</strong></div>
                <small>Overall course progress</small>
              </div>

              <div className="analytics-card calendar-card">
                <div className="card-heading"><h4>December</h4><CalendarDays size={16} /></div>
                <div className="calendar-days">
                  {Array.from({ length: 21 }, (_, index) => (
                    <span className={index === 12 ? "selected-day" : ""} key={index}>{index + 1}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <aside className="dashboard-right">
            <div className="profile-summary">
              <div className="avatar">A</div>
              <h3>Alex Thompson</h3>
              <span>Student · Level 3</span>
              <div className="profile-progress"><span /></div>
            </div>
            <div className="todo-panel">
              <div className="card-heading"><h4>To Do List</h4><CircleHelp size={15} /></div>
              {taskState.map((task, index) => (
                <button className="todo-row" key={task.title} onClick={() => toggleTask(index)}>
                  <span className={task.done ? "todo-check checked" : "todo-check"}>
                    {task.done && <Check size={12} />}
                  </span>
                  <span><strong className={task.done ? "done-text" : ""}>{task.title}</strong><small>{task.time}</small></span>
                </button>
              ))}
            </div>
          </aside>
        </div>

        <div className="trusted-strip">
          <strong>Trusted by</strong>
          <span><BookOpen size={17} /> FutureLearners</span>
          <span><GraduationCap size={17} /> SkillBridge</span>
          <span><Sparkles size={17} /> EduNext</span>
          <span><Users size={17} /> LearnHub</span>
          <span><Award size={17} /> GlobalEd</span>
        </div>
      </section>

      <section className="how-it-works" id="how-it-works">
        <div className="section-heading process-heading">
          <div><span className="section-label">HOW LEARNORA WORKS</span><h2>A simple path from curious to confident.</h2></div>
          <p>Follow a clear learning flow with small milestones, guided practice, and visible progress.</p>
        </div>
        <div className="process-track">
          <article className="process-step">
            <div className="sketch-scene"><div className="sketch-circle"><MousePointer2 size={30} /></div><span className="sketch-line line-one" /><span className="sketch-dot dot-one" /><span className="sketch-dot dot-two" /></div>
            <span className="step-number">01</span><h3>Choose your goal</h3><p>Pick a course or learning path that matches your interests.</p>
          </article>
          <div className="process-arrow"><ArrowRight size={24} /></div>
          <article className="process-step">
            <div className="sketch-scene"><div className="sketch-window"><span /><span /><span /><div className="sketch-progress" /></div><span className="sketch-pencil">✎</span></div>
            <span className="step-number">02</span><h3>Learn and practice</h3><p>Watch lessons, complete activities, and build practical skills.</p>
          </article>
          <div className="process-arrow"><ArrowRight size={24} /></div>
          <article className="process-step">
            <div className="sketch-scene"><div className="sketch-check"><CheckCircle2 size={40} /></div><span className="sketch-star">✦</span><span className="sketch-star star-two">✧</span></div>
            <span className="step-number">03</span><h3>Track your growth</h3><p>See your progress, earn milestones, and keep moving forward.</p>
          </article>
        </div>
      </section>

      <section className="capability-section" id="capabilities">
        <div className="section-heading process-heading">
          <div><span className="section-label">WHAT LEARNORA CAN DO</span><h2>Built to actually move your skills forward.</h2></div>
          <p>Four small systems working quietly behind every course, so learning sticks instead of slipping away.</p>
        </div>
        <div className="capability-grid">
          {capabilities.map((item) => (
            <article className="capability-card" key={item.key}>
              <div className={`capability-sketch sketch-${item.sketch}`}>
                {item.sketch === "map" && (
                  <>
                    <svg className="capability-path" viewBox="0 0 120 80" fill="none">
                      <path d="M8 62 C 28 62, 22 22, 44 22 S 66 58, 88 46 S 96 18, 112 18" />
                    </svg>
                    <span className="map-pin"><Route size={16} /></span>
                  </>
                )}
                {item.sketch === "terminal" && (
                  <div className="terminal-box">
                    <span className="terminal-dot" /><span className="terminal-dot" /><span className="terminal-dot" />
                    <div className="terminal-line"><TerminalSquare size={14} /><em>build_project.js</em></div>
                    <div className="terminal-caret" />
                  </div>
                )}
                {item.sketch === "chart" && (
                  <div className="mini-chart">
                    {[30, 55, 40, 70, 50, 85].map((h, i) => (
                      <span key={i} style={{ height: `${h}%`, animationDelay: `${i * 0.15}s` }} />
                    ))}
                    <SlidersHorizontal className="chart-glyph" size={16} />
                  </div>
                )}
                {item.sketch === "badge" && (
                  <div className="badge-scene">
                    <BadgeCheck size={38} />
                    <span className="badge-star star-a">✦</span>
                    <span className="badge-star star-b">✧</span>
                    <span className="badge-star star-c">✦</span>
                  </div>
                )}
              </div>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="content-section" id="courses">
        <div className="section-heading">
          <div><span className="section-label">LEARN AT YOUR PACE</span><h2>Courses for your next chapter</h2></div>
          <button className="text-button" onClick={() => openAuth("register")}>Browse all courses <ArrowRight size={16} /></button>
        </div>
        <div className="large-course-grid">
          {courses.map((course) => (
            <article className="large-course-card" key={course.title}>
              <div className={`capability-sketch course-sketch course-sketch-${course.sketch}`}>
                {course.sketch === "code" && (
                  <div className="code-sketch-box">
                    <span className="code-bracket left">{"<"}</span>
                    <span className="code-caret" />
                    <span className="code-bracket right">{">"}</span>
                  </div>
                )}
                {course.sketch === "design" && (
                  <>
                    <svg className="design-loop" viewBox="0 0 90 90" fill="none">
                      <path d="M45 8 C 70 8, 82 30, 82 45 C 82 68, 60 82, 45 82 C 22 82, 8 60, 8 45 C 8 26, 24 8, 45 8" />
                    </svg>
                    <span className="design-spark spark-one">✦</span>
                    <span className="design-spark spark-two">✧</span>
                  </>
                )}
                {course.sketch === "motion" && (
                  <div className="motion-scene">
                    <span className="motion-ring ring-a" />
                    <span className="motion-ring ring-b" />
                    <span className="motion-play"><Play size={20} /></span>
                  </div>
                )}
              </div>
              <span className="course-tag">Popular course</span>
              <h3>{course.title}</h3>
              <p>{course.subtitle}</p>
              <div className="large-course-bottom"><span><Clock3 size={14} /> 6 weeks</span><button onClick={() => openAuth("register")}>Enroll <ArrowRight size={15} /></button></div>
            </article>
          ))}
        </div>
      </section>

      <section className="content-section soft-section" id="paths">
        <div className="section-heading">
          <div><span className="section-label">STRUCTURED LEARNING</span><h2>Follow a path, not a guess</h2></div>
        </div>
        <div className="path-grid">
          <div><Code2 /><h3>Become a Developer</h3><p>Move from fundamentals to building real applications.</p></div>
          <div><Sparkles /><h3>Become a Designer</h3><p>Learn design systems, UX thinking, and prototyping.</p></div>
          <div><Trophy /><h3>Build Your Portfolio</h3><p>Complete practical projects and earn certificates.</p></div>
        </div>
      </section>

      <section className="content-section" id="instructors">
        <div className="simple-banner">
          <div><span className="section-label">EXPERT GUIDANCE</span><h2>Learn from people who build.</h2><p>Get practical knowledge from instructors and creators.</p></div>
          <button className="primary-button" onClick={() => openAuth("register")}>Meet instructors <ArrowRight size={17} /></button>
        </div>
      </section>

      <section className="content-section soft-section" id="pricing">
        <div className="pricing-card">
          <div><span className="section-label">SIMPLE PRICING</span><h2>Start learning for free.</h2><p>Explore beginner-friendly lessons. Upgrade when you are ready.</p></div>
          <div className="price"><strong>₹0</strong><span>/ starter</span></div>
          <button className="primary-button" onClick={() => openAuth("register")}>Create free account <ArrowRight size={17} /></button>
        </div>
      </section>

      <footer className="footer">
        <svg className="footer-curve" viewBox="0 0 1440 110" preserveAspectRatio="none" aria-hidden="true">
          <path d="M0,110 C 240,10 480,100 720,55 C 960,10 1200,95 1440,20 L1440,110 L0,110 Z" />
        </svg>
        <div className="footer-cta">
          <h2>Ready to <span>start?</span></h2>
          <p>Join learners building real skills with Learnora — at your pace, your way.</p>
          <button className="footer-button" onClick={() => openAuth("register")}>Start learning <ArrowRight size={17} /></button>
        </div>
        <div className="footer-grid">
          <div className="footer-about">
            <div className="brand"><span className="brand-mark"><GraduationCap size={23} /></span><span>Learnora</span></div>
            <p>Learn without limits. Build skills for tomorrow.</p>
            <div className="social-links"><button aria-label="Instagram"><Instagram size={18} /></button><button aria-label="Twitter"><Twitter size={18} /></button><button aria-label="YouTube"><Youtube size={18} /></button></div>
          </div>
          <div><h4>Explore</h4><button onClick={() => scrollTo("courses")}>Courses</button><button onClick={() => scrollTo("paths")}>Learning Paths</button><button onClick={() => scrollTo("pricing")}>Pricing</button></div>
          <div><h4>Company</h4><button onClick={() => scrollTo("instructors")}>Instructors</button><button onClick={() => scrollTo("how-it-works")}>How it works</button><button onClick={() => scrollTo("home")}>Home</button></div>
          <div><h4>Contact</h4><a href="mailto:support@learnora.example"><Mail size={14} /> support@learnora.example</a><a href="tel:+918001234567"><Phone size={14} /> +91 800 123 4567</a></div>
        </div>
        <div className="footer-bottom"><span>Made for curious minds.</span><span>© 2026 Learnora. All rights reserved.</span></div>
      </footer>
    </main>
  );
}

function AuthPage({
  mode,
  setMode,
  email,
  setEmail,
  password,
  setPassword,
  name,
  setName,
  showPassword,
  setShowPassword,
  onSubmit,
  onBack,
  loading
}) {
  return (
    <main className="auth-page">
      <div className="auth-visual">
        <div className="auth-ambient auth-ambient-one" />
        <div className="auth-ambient auth-ambient-two" />
        <div className="auth-ambient auth-ambient-three" />
        <div className="auth-float auth-float-one"><BookOpen size={26} /></div>
        <div className="auth-float auth-float-two"><Code2 size={22} /></div>
        <div className="auth-float auth-float-three"><Sparkles size={20} /></div>
        <div className="auth-float auth-float-four"><Trophy size={24} /></div>
        <div className="auth-float auth-float-five">✎</div>
        <div className="auth-ring auth-ring-one" />
        <div className="auth-ring auth-ring-two" />

        <button className="brand auth-brand" onClick={onBack}>
          <span className="brand-mark"><GraduationCap size={23} /></span>
          <span>Learnora</span>
        </button>

        <div className="auth-visual-copy">
          <h2>Your future starts with one small step.</h2>
          <p>Join a community building real, practical skills every day — one guided lesson at a time.</p>
        </div>
      </div>

      <div className="auth-form-side">
        <button className="auth-back" onClick={onBack}><ArrowLeft size={16} /> Back to home</button>

        <div className="auth-card">
          <div className="auth-icon"><GraduationCap size={25} /></div>

          <div className="auth-tabs">
            <button className={mode === "login" ? "auth-tab active" : "auth-tab"} onClick={() => setMode("login")}>Sign in</button>
            <button className={mode === "register" ? "auth-tab active" : "auth-tab"} onClick={() => setMode("register")}>Create account</button>
            <span className={mode === "login" ? "auth-tab-slider" : "auth-tab-slider slide-right"} />
          </div>

          <h2 className="auth-title">{mode === "login" ? "Welcome back" : "Start your learning journey"}</h2>
          <p className="auth-subtitle">{mode === "login" ? "Log in to pick up right where you left off." : "Create a free account to explore courses."}</p>

          <form onSubmit={onSubmit} key={mode} className="auth-form">
            {mode === "register" && (
              <label className="input-field">
                <User size={16} />
                <input type="text" value={name} onChange={(event) => setName(event.target.value)} placeholder="Full name" required />
              </label>
            )}
            <label className="input-field">
              <Mail size={16} />
              <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" required />
            </label>
            <label className="input-field">
              <Lock size={16} />
              <input type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter password" minLength={4} required />
              <button type="button" className="toggle-visibility" onClick={() => setShowPassword((value) => !value)} aria-label="Toggle password visibility">
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </label>

            <button className="primary-button full-button" type="submit" disabled={loading}>
              {loading ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
              {!loading && <ArrowRight size={17} />}
            </button>
          </form>

          <button className="switch-auth" onClick={() => setMode(mode === "login" ? "register" : "login")}>
            {mode === "login" ? "New here? Create an account" : "Already have an account? Log in"}
          </button>
          <small className="demo-note">Demo mode: any valid email and 4+ character password will work.</small>
        </div>
      </div>
    </main>
  );
}

function DashboardPage({ displayName, searchTerm, setSearchTerm, filteredCourses, taskState, toggleTask, onLogout, onHome }) {
  const initial = displayName.trim().charAt(0).toUpperCase() || "A";

  return (
    <main className="app-dashboard">
      <aside className="app-sidebar">
        <button className="mini-brand home-link" onClick={onHome} title="Back to home — you'll stay signed in">
          <GraduationCap size={18} /> Learnora
        </button>
        <button className="side-item active"><LayoutDashboard size={16} /> Dashboard</button>
        <button className="side-item"><BookOpen size={16} /> My Courses</button>
        <button className="side-item"><Trophy size={16} /> Learning Paths</button>
        <button className="side-item"><Check size={16} /> Assignments</button>
        <button className="side-item"><ChartNoAxesColumnIncreasing size={16} /> Progress</button>
        <button className="side-item"><Bell size={16} /> Notifications</button>
        <button className="side-item home-item" onClick={onHome}><ArrowLeft size={16} /> Back to home</button>
        <button className="side-item logout-item" onClick={onLogout}><LogOut size={16} /> Log out</button>
      </aside>

      <div className="app-main">
        <div className="app-topbar">
          <div>
            <h3>Hello, {displayName.split(" ")[0]} 👋</h3>
            <span>Let’s learn something new today!</span>
          </div>
          <div className="dashboard-search">
            <Search size={16} />
            <input
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Search courses..."
              aria-label="Search courses"
            />
          </div>
          <button className="icon-button" aria-label="Notifications"><Bell size={17} /></button>
        </div>

        <div className="course-heading">
          <h3>My Courses</h3>
          <button>View all <ChevronRight size={14} /></button>
        </div>

        <div className="course-grid">
          {filteredCourses.map((course) => {
            const Icon = course.icon;
            return (
              <article className={`mini-course ${course.tone}`} key={course.title}>
                <div className="course-icon"><Icon size={20} /></div>
                <h4>{course.title}</h4>
                <p>{course.subtitle}</p>
                <div className="progress-line"><span style={{ width: `${course.progress}%` }} /></div>
                <div className="course-meta"><span>{course.progress}% complete</span><ChevronRight size={14} /></div>
              </article>
            );
          })}
          {filteredCourses.length === 0 && <p className="empty-state">No courses found.</p>}
        </div>

        <div className="analytics-grid">
          <div className="analytics-card">
            <div className="card-heading"><h4>Weekly Learning Progress</h4><span>+24%</span></div>
            <div className="bar-chart">
              {[35, 52, 74, 46, 67, 56, 83].map((height, index) => (
                <div className="bar-column" key={index}>
                  <span style={{ height: `${height}%` }} />
                  <small>{["M", "T", "W", "T", "F", "S", "S"][index]}</small>
                </div>
              ))}
            </div>
          </div>

          <div className="analytics-card performance-card">
            <div className="card-heading"><h4>Your Performance</h4><Trophy size={16} /></div>
            <div className="score-ring"><strong>92%</strong></div>
            <small>Overall course progress</small>
          </div>

          <div className="analytics-card calendar-card">
            <div className="card-heading"><h4>December</h4><CalendarDays size={16} /></div>
            <div className="calendar-days">
              {Array.from({ length: 21 }, (_, index) => (
                <span className={index === 12 ? "selected-day" : ""} key={index}>{index + 1}</span>
              ))}
            </div>
          </div>
        </div>
      </div>

      <aside className="app-right">
        <div className="profile-summary">
          <div className="avatar">{initial}</div>
          <h3>{displayName}</h3>
          <span>Student · Level 3</span>
          <div className="profile-progress"><span /></div>
        </div>
        <div className="todo-panel">
          <div className="card-heading"><h4>To Do List</h4><CircleHelp size={15} /></div>
          {taskState.map((task, index) => (
            <button className="todo-row" key={task.title} onClick={() => toggleTask(index)}>
              <span className={task.done ? "todo-check checked" : "todo-check"}>
                {task.done && <Check size={12} />}
              </span>
              <span><strong className={task.done ? "done-text" : ""}>{task.title}</strong><small>{task.time}</small></span>
            </button>
          ))}
        </div>
      </aside>
    </main>
  );
}

export default App;