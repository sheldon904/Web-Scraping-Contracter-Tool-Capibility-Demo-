import {
  pgTable,
  uuid,
  text,
  varchar,
  timestamp,
  date,
  boolean,
  integer,
  numeric,
  jsonb,
  index,
  check,
} from "drizzle-orm/pg-core";
import { relations, sql } from "drizzle-orm";

// ============================================================================
// Companies - Central entity
// ============================================================================
export const companies = pgTable(
  "companies",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    name: varchar("name", { length: 255 }).notNull(),
    normalizedName: varchar("normalized_name", { length: 255 }).notNull(),
    state: varchar("state", { length: 2 }).default("FL"),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow(),
  },
  (table) => ({
    normalizedNameIdx: index("idx_companies_normalized_name").on(table.normalizedName),
  })
);

export const companiesRelations = relations(companies, ({ many }) => ({
  licenses: many(licenses),
  reviews: many(reviews),
  bbbProfiles: many(bbbProfiles),
  courtCases: many(courtCases),
  liens: many(liens),
  riskScores: many(riskScores),
  scrapeJobs: many(scrapeJobs),
  reports: many(reports),
}));

// ============================================================================
// Licenses - Florida DBPR license data
// ============================================================================
export const licenses = pgTable(
  "licenses",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    companyId: uuid("company_id")
      .notNull()
      .references(() => companies.id, { onDelete: "cascade" }),
    licenseNumber: varchar("license_number", { length: 50 }).notNull(),
    licenseType: varchar("license_type", { length: 100 }),
    status: varchar("status", { length: 50 }),
    issueDate: date("issue_date"),
    expirationDate: date("expiration_date"),
    licenseeName: varchar("licensee_name", { length: 255 }),
    address: text("address"),
    source: varchar("source", { length: 50 }).default("FL_DBPR"),
    rawData: jsonb("raw_data"),
    scrapedAt: timestamp("scraped_at", { withTimezone: true }).defaultNow(),
  },
  (table) => ({
    companyIdx: index("idx_licenses_company").on(table.companyId),
    statusIdx: index("idx_licenses_status").on(table.status),
    expirationIdx: index("idx_licenses_expiration").on(table.expirationDate),
  })
);

export const licensesRelations = relations(licenses, ({ one, many }) => ({
  company: one(companies, {
    fields: [licenses.companyId],
    references: [companies.id],
  }),
  disciplinaryActions: many(disciplinaryActions),
}));

// ============================================================================
// Disciplinary Actions - License violations
// ============================================================================
export const disciplinaryActions = pgTable(
  "disciplinary_actions",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    licenseId: uuid("license_id")
      .notNull()
      .references(() => licenses.id, { onDelete: "cascade" }),
    actionType: varchar("action_type", { length: 100 }),
    actionDate: date("action_date"),
    description: text("description"),
    fineAmount: numeric("fine_amount", { precision: 10, scale: 2 }),
    resolution: text("resolution"),
    caseNumber: varchar("case_number", { length: 100 }),
    rawData: jsonb("raw_data"),
    scrapedAt: timestamp("scraped_at", { withTimezone: true }).defaultNow(),
  },
  (table) => ({
    licenseIdx: index("idx_disciplinary_license").on(table.licenseId),
    dateIdx: index("idx_disciplinary_date").on(table.actionDate),
  })
);

export const disciplinaryActionsRelations = relations(disciplinaryActions, ({ one }) => ({
  license: one(licenses, {
    fields: [disciplinaryActions.licenseId],
    references: [licenses.id],
  }),
}));

// ============================================================================
// Reviews - Generic reviews (Google, Yelp, etc.)
// ============================================================================
export const reviews = pgTable(
  "reviews",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    companyId: uuid("company_id")
      .notNull()
      .references(() => companies.id, { onDelete: "cascade" }),
    source: varchar("source", { length: 50 }).notNull(),
    rating: numeric("rating", { precision: 2, scale: 1 }),
    reviewCount: integer("review_count"),
    reviewText: text("review_text"),
    reviewerName: varchar("reviewer_name", { length: 255 }),
    reviewDate: date("review_date"),
    responseText: text("response_text"),
    externalId: varchar("external_id", { length: 255 }),
    rawData: jsonb("raw_data"),
    scrapedAt: timestamp("scraped_at", { withTimezone: true }).defaultNow(),
  },
  (table) => ({
    companyIdx: index("idx_reviews_company").on(table.companyId),
    sourceIdx: index("idx_reviews_source").on(table.source),
    ratingIdx: index("idx_reviews_rating").on(table.rating),
  })
);

export const reviewsRelations = relations(reviews, ({ one }) => ({
  company: one(companies, {
    fields: [reviews.companyId],
    references: [companies.id],
  }),
}));

// ============================================================================
// BBB Profiles - Better Business Bureau specific data
// ============================================================================
export const bbbProfiles = pgTable(
  "bbb_profiles",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    companyId: uuid("company_id")
      .notNull()
      .references(() => companies.id, { onDelete: "cascade" }),
    bbbRating: varchar("bbb_rating", { length: 5 }),
    accredited: boolean("accredited").default(false),
    yearsInBusiness: integer("years_in_business"),
    complaintCount: integer("complaint_count"),
    complaintResolvedCount: integer("complaint_resolved_count"),
    complaintUnresolvedCount: integer("complaint_unresolved_count"),
    governmentActionsCount: integer("government_actions_count"),
    profileUrl: text("profile_url"),
    rawData: jsonb("raw_data"),
    scrapedAt: timestamp("scraped_at", { withTimezone: true }).defaultNow(),
  },
  (table) => ({
    companyIdx: index("idx_bbb_company").on(table.companyId),
  })
);

export const bbbProfilesRelations = relations(bbbProfiles, ({ one }) => ({
  company: one(companies, {
    fields: [bbbProfiles.companyId],
    references: [companies.id],
  }),
}));

// ============================================================================
// Court Cases - Federal court records from CourtListener
// ============================================================================
export const courtCases = pgTable(
  "court_cases",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    companyId: uuid("company_id")
      .notNull()
      .references(() => companies.id, { onDelete: "cascade" }),
    source: varchar("source", { length: 50 }),
    caseNumber: varchar("case_number", { length: 100 }),
    caseType: varchar("case_type", { length: 100 }),
    courtName: varchar("court_name", { length: 255 }),
    filingDate: date("filing_date"),
    status: varchar("status", { length: 100 }),
    plaintiff: varchar("plaintiff", { length: 500 }),
    defendant: varchar("defendant", { length: 500 }),
    caseSummary: text("case_summary"),
    judgmentAmount: numeric("judgment_amount", { precision: 12, scale: 2 }),
    externalUrl: text("external_url"),
    rawData: jsonb("raw_data"),
    scrapedAt: timestamp("scraped_at", { withTimezone: true }).defaultNow(),
  },
  (table) => ({
    companyIdx: index("idx_court_company").on(table.companyId),
    typeIdx: index("idx_court_type").on(table.caseType),
    dateIdx: index("idx_court_date").on(table.filingDate),
  })
);

export const courtCasesRelations = relations(courtCases, ({ one }) => ({
  company: one(companies, {
    fields: [courtCases.companyId],
    references: [companies.id],
  }),
}));

// ============================================================================
// Liens - UCC filings and secured transactions
// ============================================================================
export const liens = pgTable(
  "liens",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    companyId: uuid("company_id")
      .notNull()
      .references(() => companies.id, { onDelete: "cascade" }),
    lienType: varchar("lien_type", { length: 50 }),
    filingNumber: varchar("filing_number", { length: 100 }),
    filingDate: date("filing_date"),
    securedParty: varchar("secured_party", { length: 500 }),
    collateralDescription: text("collateral_description"),
    amount: numeric("amount", { precision: 12, scale: 2 }),
    status: varchar("status", { length: 50 }),
    source: varchar("source", { length: 50 }),
    rawData: jsonb("raw_data"),
    scrapedAt: timestamp("scraped_at", { withTimezone: true }).defaultNow(),
  },
  (table) => ({
    companyIdx: index("idx_liens_company").on(table.companyId),
    statusIdx: index("idx_liens_status").on(table.status),
  })
);

export const liensRelations = relations(liens, ({ one }) => ({
  company: one(companies, {
    fields: [liens.companyId],
    references: [companies.id],
  }),
}));

// ============================================================================
// Risk Scores - Calculated risk assessments
// ============================================================================
export const riskScores = pgTable(
  "risk_scores",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    companyId: uuid("company_id")
      .notNull()
      .references(() => companies.id, { onDelete: "cascade" }),
    overallScore: integer("overall_score"),
    licenseScore: integer("license_score"),
    reputationScore: integer("reputation_score"),
    litigationScore: integer("litigation_score"),
    financialScore: integer("financial_score"),
    confidenceLevel: numeric("confidence_level", { precision: 3, scale: 2 }),
    scoreBreakdown: jsonb("score_breakdown"),
    dataCompleteness: jsonb("data_completeness"),
    calculatedAt: timestamp("calculated_at", { withTimezone: true }).defaultNow(),
    version: varchar("version", { length: 20 }).default("1.0"),
  },
  (table) => ({
    companyIdx: index("idx_risk_scores_company").on(table.companyId),
    overallIdx: index("idx_risk_scores_overall").on(table.overallScore),
    dateIdx: index("idx_risk_scores_date").on(table.calculatedAt),
  })
);

export const riskScoresRelations = relations(riskScores, ({ one, many }) => ({
  company: one(companies, {
    fields: [riskScores.companyId],
    references: [companies.id],
  }),
  reports: many(reports),
}));

// ============================================================================
// Scrape Jobs - Job tracking for scraping operations
// ============================================================================
export const scrapeJobs = pgTable(
  "scrape_jobs",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    companyId: uuid("company_id")
      .notNull()
      .references(() => companies.id, { onDelete: "cascade" }),
    source: varchar("source", { length: 50 }).notNull(),
    status: varchar("status", { length: 20 }).default("pending"),
    startedAt: timestamp("started_at", { withTimezone: true }),
    completedAt: timestamp("completed_at", { withTimezone: true }),
    errorMessage: text("error_message"),
    retryCount: integer("retry_count").default(0),
    jobMetadata: jsonb("job_metadata"),
  },
  (table) => ({
    companyIdx: index("idx_scrape_jobs_company").on(table.companyId),
    statusIdx: index("idx_scrape_jobs_status").on(table.status),
  })
);

export const scrapeJobsRelations = relations(scrapeJobs, ({ one }) => ({
  company: one(companies, {
    fields: [scrapeJobs.companyId],
    references: [companies.id],
  }),
}));

// ============================================================================
// Reports - Generated report metadata
// ============================================================================
export const reports = pgTable(
  "reports",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    companyId: uuid("company_id")
      .notNull()
      .references(() => companies.id, { onDelete: "cascade" }),
    riskScoreId: uuid("risk_score_id").references(() => riskScores.id),
    format: varchar("format", { length: 10 }).notNull(),
    filePath: text("file_path"),
    generatedAt: timestamp("generated_at", { withTimezone: true }).defaultNow(),
  },
  (table) => ({
    companyIdx: index("idx_reports_company").on(table.companyId),
  })
);

export const reportsRelations = relations(reports, ({ one }) => ({
  company: one(companies, {
    fields: [reports.companyId],
    references: [companies.id],
  }),
  riskScore: one(riskScores, {
    fields: [reports.riskScoreId],
    references: [riskScores.id],
  }),
}));

// ============================================================================
// Type exports for use in application code
// ============================================================================
export type Company = typeof companies.$inferSelect;
export type NewCompany = typeof companies.$inferInsert;

export type License = typeof licenses.$inferSelect;
export type NewLicense = typeof licenses.$inferInsert;

export type DisciplinaryAction = typeof disciplinaryActions.$inferSelect;
export type NewDisciplinaryAction = typeof disciplinaryActions.$inferInsert;

export type Review = typeof reviews.$inferSelect;
export type NewReview = typeof reviews.$inferInsert;

export type BBBProfile = typeof bbbProfiles.$inferSelect;
export type NewBBBProfile = typeof bbbProfiles.$inferInsert;

export type CourtCase = typeof courtCases.$inferSelect;
export type NewCourtCase = typeof courtCases.$inferInsert;

export type Lien = typeof liens.$inferSelect;
export type NewLien = typeof liens.$inferInsert;

export type RiskScore = typeof riskScores.$inferSelect;
export type NewRiskScore = typeof riskScores.$inferInsert;

export type ScrapeJob = typeof scrapeJobs.$inferSelect;
export type NewScrapeJob = typeof scrapeJobs.$inferInsert;

export type Report = typeof reports.$inferSelect;
export type NewReport = typeof reports.$inferInsert;
