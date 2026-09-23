type FirebaseConfig = {
  apiKey: string;
  authDomain: string;
  projectId: string;
};

export async function signInWithGoogle(config: FirebaseConfig): Promise<string> {
  const { initializeApp } = await import("firebase/app");
  const { getAuth, GoogleAuthProvider, signInWithPopup } = await import("firebase/auth");

  const app = initializeApp({
    apiKey: config.apiKey,
    authDomain: config.authDomain,
    projectId: config.projectId,
  });
  const auth = getAuth(app);
  const provider = new GoogleAuthProvider();
  const result = await signInWithPopup(auth, provider);
  const token = await result.user.getIdToken();
  return token;
}
