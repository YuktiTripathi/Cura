export type HomeVisit = {
  lastSeenAt: string;
  previousVisitAt: string | null;
  seenReportIds: string[];
};

function key(userId: string) {
  return `cura_home:${userId}`;
}

function sessionKey(userId: string) {
  return `cura_home_session:${userId}`;
}

export function readVisit(userId: string, now: string, storage: Storage, session: Storage): HomeVisit {
  const raw = storage.getItem(key(userId));
  const stored: HomeVisit = raw
    ? (JSON.parse(raw) as HomeVisit)
    : { lastSeenAt: now, previousVisitAt: null, seenReportIds: [] };
  if (!session.getItem(sessionKey(userId))) {
    const next: HomeVisit = {
      lastSeenAt: now,
      previousVisitAt: raw ? stored.lastSeenAt : null,
      seenReportIds: stored.seenReportIds || [],
    };
    storage.setItem(key(userId), JSON.stringify(next));
    session.setItem(sessionKey(userId), "1");
    return next;
  }
  return {
    lastSeenAt: stored.lastSeenAt || now,
    previousVisitAt: stored.previousVisitAt ?? null,
    seenReportIds: stored.seenReportIds || [],
  };
}

export function markReportsExplored(userId: string, reportIds: string[], storage: Storage) {
  const raw = storage.getItem(key(userId));
  const stored: HomeVisit = raw
    ? (JSON.parse(raw) as HomeVisit)
    : { lastSeenAt: new Date().toISOString(), previousVisitAt: null, seenReportIds: [] };
  const seen = new Set([...(stored.seenReportIds || []), ...reportIds.filter(Boolean)]);
  storage.setItem(key(userId), JSON.stringify({ ...stored, seenReportIds: [...seen] }));
}
