import Link from "next/link";
import { SignInButton, SignUpButton, SignedIn, SignedOut } from "@clerk/nextjs";
import {
  Github,
  Zap,
  Target,
  Clock,
  CheckSquare,
  MessageSquare,
  BarChart3,
  ArrowRight,
  Bot,
} from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Nav */}
      <nav className="flex items-center justify-between p-6 max-w-7xl mx-auto">
        <div className="flex items-center gap-2">
          <Bot className="w-7 h-7 text-violet-400" />
          <span className="text-xl font-bold tracking-tight">Hackathon Navigator</span>
        </div>
        <div className="flex items-center gap-4">
          <SignedOut>
            <SignInButton mode="modal">
              <button className="text-gray-400 hover:text-white transition-colors text-sm">
                Sign in
              </button>
            </SignInButton>
            <SignUpButton mode="modal">
              <button className="bg-violet-600 hover:bg-violet-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                Get started free
              </button>
            </SignUpButton>
          </SignedOut>
          <SignedIn>
            <Link
              href="/dashboard"
              className="bg-violet-600 hover:bg-violet-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
            >
              Dashboard <ArrowRight className="w-4 h-4" />
            </Link>
          </SignedIn>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-5xl mx-auto px-6 pt-20 pb-32 text-center">
        <div className="inline-flex items-center gap-2 bg-violet-950/60 border border-violet-800/50 rounded-full px-4 py-1.5 text-violet-300 text-sm mb-8">
          <Zap className="w-3.5 h-3.5" />
          <span>Powered by Claude + LangGraph multi-agent system</span>
        </div>

        <h1 className="text-5xl sm:text-7xl font-black tracking-tight mb-6 bg-gradient-to-br from-white via-gray-200 to-gray-400 bg-clip-text text-transparent">
          Your AI teammate
          <br />
          for every hackathon
        </h1>

        <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-10 leading-relaxed">
          Connect your GitHub repo. Set your deadline. Our AI analyzes your codebase,
          plans your tasks, coaches your pitch, and keeps you on track to ship.
        </p>

        <div className="flex items-center justify-center gap-4 flex-wrap">
          <SignUpButton mode="modal">
            <button className="bg-violet-600 hover:bg-violet-500 text-white px-8 py-3.5 rounded-xl text-base font-semibold transition-all hover:scale-105 flex items-center gap-2">
              Start your project <ArrowRight className="w-4 h-4" />
            </button>
          </SignUpButton>
          <a
            href="https://github.com"
            className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors px-6 py-3.5 border border-gray-800 rounded-xl hover:border-gray-600"
          >
            <Github className="w-4 h-4" />
            View on GitHub
          </a>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-6 pb-24">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((feature) => (
            <div
              key={feature.title}
              className="bg-gray-900/60 border border-gray-800 rounded-2xl p-6 hover:border-gray-700 transition-colors"
            >
              <div className={`w-10 h-10 ${feature.iconBg} rounded-xl flex items-center justify-center mb-4`}>
                <feature.Icon className={`w-5 h-5 ${feature.iconColor}`} />
              </div>
              <h3 className="text-white font-semibold mb-2">{feature.title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">{feature.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Agent Pipeline */}
      <section className="max-w-4xl mx-auto px-6 pb-24">
        <h2 className="text-2xl font-bold text-center mb-3">5 agents, one mission</h2>
        <p className="text-gray-400 text-center mb-10 text-sm">Each agent specializes in a different domain and runs in sequence</p>
        <div className="flex flex-col sm:flex-row items-center gap-0">
          {AGENTS.map((agent, i) => (
            <div key={agent.name} className="flex items-center gap-0 w-full sm:w-auto">
              <div className={`flex-1 sm:flex-none ${agent.bg} border ${agent.border} rounded-xl p-4 text-center sm:w-32`}>
                <div className="text-2xl mb-1">{agent.emoji}</div>
                <div className={`text-xs font-semibold ${agent.textColor}`}>{agent.name}</div>
                <div className="text-gray-500 text-xs mt-1">{agent.role}</div>
              </div>
              {i < AGENTS.length - 1 && (
                <ArrowRight className="text-gray-700 mx-1 flex-shrink-0 hidden sm:block" />
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-900 py-8 text-center text-gray-600 text-sm">
        <p>Built with Claude Sonnet, LangGraph, Next.js 15, FastAPI</p>
      </footer>
    </div>
  );
}

const FEATURES = [
  {
    title: "Repository Intelligence",
    description: "Deep analysis of your GitHub repo — structure, architecture, tech stack, PRs, issues, and contributor activity.",
    Icon: Github,
    iconBg: "bg-gray-800",
    iconColor: "text-gray-300",
  },
  {
    title: "Smart Task Planner",
    description: "AI generates a prioritized task list optimized for your deadline and judging criteria. Blockers flagged immediately.",
    Icon: CheckSquare,
    iconBg: "bg-violet-950",
    iconColor: "text-violet-400",
  },
  {
    title: "Technical Reviewer",
    description: "Spots bugs, performance risks, missing integrations, and quick wins in your codebase.",
    Icon: Target,
    iconBg: "bg-blue-950",
    iconColor: "text-blue-400",
  },
  {
    title: "Pitch Coach",
    description: "Generates Devpost submissions, elevator pitches, demo scripts, and architecture explanations tailored to your judges.",
    Icon: MessageSquare,
    iconBg: "bg-green-950",
    iconColor: "text-green-400",
  },
  {
    title: "Deadline Intelligence",
    description: "Tracks your remaining work, estimates time to completion, and recommends scope reductions when needed.",
    Icon: Clock,
    iconBg: "bg-orange-950",
    iconColor: "text-orange-400",
  },
  {
    title: "Progress Analytics",
    description: "Visual dashboards showing completion %, risk level, commit frequency, and team activity over time.",
    Icon: BarChart3,
    iconBg: "bg-pink-950",
    iconColor: "text-pink-400",
  },
];

const AGENTS = [
  { name: "Repo Analyst", role: "GitHub + RAG", emoji: "🔍", bg: "bg-violet-950/60", border: "border-violet-800/50", textColor: "text-violet-300" },
  { name: "Planner", role: "Tasks + Priority", emoji: "📋", bg: "bg-blue-950/60", border: "border-blue-800/50", textColor: "text-blue-300" },
  { name: "Tech Reviewer", role: "Code + Arch", emoji: "⚙️", bg: "bg-teal-950/60", border: "border-teal-800/50", textColor: "text-teal-300" },
  { name: "Pitch Coach", role: "Devpost + Demo", emoji: "🎤", bg: "bg-green-950/60", border: "border-green-800/50", textColor: "text-green-300" },
  { name: "Deadline Mgr", role: "Risk + Scope", emoji: "⏱️", bg: "bg-orange-950/60", border: "border-orange-800/50", textColor: "text-orange-300" },
];
