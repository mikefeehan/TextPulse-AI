"use client";

import { Fragment } from "react";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type {
  AnalyticsSeriesPoint,
  EmojiStat,
  HeatMapCell,
  TopicStat,
} from "@/lib/types";

export function StoryLineChart({
  data,
  userLabel = "You",
  contactLabel = "Them",
}: {
  data: AnalyticsSeriesPoint[];
  userLabel?: string;
  contactLabel?: string;
}) {
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid stroke="rgba(148, 163, 184, 0.12)" vertical={false} />
          <XAxis dataKey="label" tick={{ fill: "#94a3b8", fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} axisLine={false} tickLine={false} />
          <Tooltip
            contentStyle={{
              background: "#111827",
              border: "1px solid rgba(148,163,184,0.18)",
              borderRadius: "16px",
              color: "#e5eef8",
            }}
          />
          <Line type="monotone" dataKey="user_count" stroke="#5eead4" strokeWidth={3} dot={false} name={userLabel} />
          <Line type="monotone" dataKey="contact_count" stroke="#f59e0b" strokeWidth={3} dot={false} name={contactLabel} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function TrendAreaChart({ data }: { data: AnalyticsSeriesPoint[] }) {
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="userArea" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#67e8f9" stopOpacity={0.55} />
              <stop offset="100%" stopColor="#67e8f9" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="contactArea" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#fbbf24" stopOpacity={0.45} />
              <stop offset="100%" stopColor="#fbbf24" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="rgba(148, 163, 184, 0.12)" vertical={false} />
          <XAxis dataKey="label" tick={{ fill: "#94a3b8", fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} axisLine={false} tickLine={false} />
          <Tooltip
            contentStyle={{
              background: "#111827",
              border: "1px solid rgba(148,163,184,0.18)",
              borderRadius: "16px",
              color: "#e5eef8",
            }}
          />
          <Area type="monotone" dataKey="user_count" stroke="#67e8f9" fill="url(#userArea)" strokeWidth={2.5} />
          <Area type="monotone" dataKey="contact_count" stroke="#fbbf24" fill="url(#contactArea)" strokeWidth={2.5} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function DistributionBars({ data }: { data: AnalyticsSeriesPoint[] }) {
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <BarChart data={data}>
          <CartesianGrid stroke="rgba(148, 163, 184, 0.12)" vertical={false} />
          <XAxis dataKey="label" tick={{ fill: "#94a3b8", fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} axisLine={false} tickLine={false} />
          <Tooltip
            contentStyle={{
              background: "#111827",
              border: "1px solid rgba(148,163,184,0.18)",
              borderRadius: "16px",
              color: "#e5eef8",
            }}
          />
          <Bar dataKey="user_count" fill="#2dd4bf" radius={[10, 10, 0, 0]} />
          <Bar dataKey="contact_count" fill="#f59e0b" radius={[10, 10, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function HeatMap({ data }: { data: HeatMapCell[] }) {
  const max = Math.max(...data.map((cell) => cell.count), 1);
  return (
    <div className="grid grid-cols-8 gap-2 text-xs text-slate-300">
      <div />
      {Array.from({ length: 7 }).map((_, hour) => (
        <div key={hour} className="text-center text-[10px] text-slate-500">
          {hour * 3}:00
        </div>
      ))}
      {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => (
        <Fragment key={day}>
          <div key={`${day}-label`} className="self-center text-[11px] text-slate-400">
            {day}
          </div>
          {Array.from({ length: 7 }).map((_, step) => {
            const hour = step * 3;
            const total = data
              .filter((cell) => cell.day === day && cell.hour >= hour && cell.hour < hour + 3)
              .reduce((sum, cell) => sum + cell.count, 0);
            const intensity = total / max;
            return (
              <div
                key={`${day}-${hour}`}
                className="h-10 rounded-2xl border border-white/6"
                style={{
                  background: `rgba(94, 234, 212, ${Math.max(0.08, intensity)})`,
                }}
                title={`${day} ${hour}:00 - ${total} messages`}
              />
            );
          })}
        </Fragment>
      ))}
    </div>
  );
}

export function RankedTopics({ topics }: { topics: TopicStat[] }) {
  const max = Math.max(...topics.map((topic) => topic.count), 1);
  return (
    <div className="space-y-3">
      {topics.map((topic) => (
        <div key={topic.label} className="space-y-1">
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-200">{topic.label}</span>
            <span className="text-slate-400">{topic.count}</span>
          </div>
          <div className="h-2 rounded-full bg-white/6">
            <div
              className="h-2 rounded-full bg-gradient-to-r from-cyan-300 via-teal-300 to-amber-300"
              style={{ width: `${(topic.count / max) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function EmojiCloud({ data }: { data: EmojiStat[] }) {
  return (
    <div className="flex flex-wrap gap-3">
      {data.map((item, index) => (
        <div
          key={item.emoji}
          className="rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3"
          style={{ transform: `scale(${1 + index * 0.03})` }}
        >
          <div className="text-2xl">{item.emoji}</div>
          <div className="mt-1 text-center text-xs text-slate-400">{item.count} uses</div>
        </div>
      ))}
    </div>
  );
}
