export const ACCESS_COOKIE_NAME = "ii_access";

// 고엔트로피 접근 코드의 SHA-256만 저장한다. 원문은 코드나 브라우저 번들에 넣지 않는다.
// SITE_ACCESS_HASH를 설정하면 배포 설정만으로 코드를 교체할 수 있다.
const DEFAULT_ACCESS_HASH = "2156aefb8c63d4b601f8354ea392867fd552dae01233f8efd5f739e3e1cdeb5b";

export const accessHash =
  process.env.SITE_ACCESS_HASH?.trim().toLowerCase() || DEFAULT_ACCESS_HASH;

const toHex = (bytes: Uint8Array) =>
  Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");

export async function hashAccessCode(value: string): Promise<string> {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value)
  );
  return toHex(new Uint8Array(digest));
}

export async function isValidAccessCode(value?: string | null): Promise<boolean> {
  if (!value || value.length > 256) return false;
  const candidate = await hashAccessCode(value);
  if (candidate.length !== accessHash.length) return false;

  // 문자열 조기 종료로 인한 불필요한 타이밍 차이를 피한다.
  let difference = 0;
  for (let index = 0; index < candidate.length; index += 1) {
    difference |= candidate.charCodeAt(index) ^ accessHash.charCodeAt(index);
  }
  return difference === 0;
}
