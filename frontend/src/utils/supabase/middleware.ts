import { type NextRequest, NextResponse } from "next/server";

export const updateSession = async (request: NextRequest) => {
  return NextResponse.next({ request: { headers: request.headers } });
};
