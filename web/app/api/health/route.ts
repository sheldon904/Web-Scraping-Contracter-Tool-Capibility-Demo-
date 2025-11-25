import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    status: "healthy",
    timestamp: new Date().toISOString(),
    version: "0.1.0",
    services: {
      database: "not_configured", // Will be updated when Neon is connected
      browserless: "not_configured", // Will be updated when Browserless is connected
    },
  });
}
