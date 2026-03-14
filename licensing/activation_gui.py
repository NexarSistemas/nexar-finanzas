"""
activation_gui.py
Pantalla de bienvenida que aparece la primera vez que el usuario
abre la app sin licencia registrada.
Ofrece dos opciones: continuar en DEMO o indicar que ya tiene una clave.
"""

import tkinter as tk
from tkinter import font as tkfont


class WelcomeWindow:
    """
    Ventana de bienvenida para usuarios nuevos (sin licencia previa).
    Se muestra UNA SOLA VEZ — cuando nunca se registró ninguna licencia.
    """

    # Resultado de la elección del usuario
    # "demo"    → continuar en DEMO
    # "activate" → el usuario dice que ya tiene una clave (arranca en DEMO
    #              pero se le recuerda que puede activar desde la app)
    choice = "demo"

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Finanzas del Hogar")
        self.root.resizable(False, False)
        self._center(480, 340)
        self.root.configure(bg="#ffffff")

        # Impedir cierre con la X sin elegir — forzar una opción
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):

        # ── Encabezado ────────────────────────────────────────
        header = tk.Frame(self.root, bg="#1a73e8", height=8)
        header.pack(fill="x")

        tk.Label(
            self.root,
            text="💰",
            font=("", 36),
            bg="#ffffff"
        ).pack(pady=(22, 4))

        tk.Label(
            self.root,
            text="Finanzas del Hogar",
            font=("", 16, "bold"),
            fg="#1a1a1a",
            bg="#ffffff"
        ).pack()

        tk.Label(
            self.root,
            text="Bienvenido — gestión de finanzas personales",
            font=("", 9),
            fg="#666666",
            bg="#ffffff"
        ).pack(pady=(2, 16))

        # ── Separador ─────────────────────────────────────────
        tk.Frame(self.root, bg="#e0e0e0", height=1).pack(fill="x", padx=30)

        # ── Mensaje ───────────────────────────────────────────
        tk.Label(
            self.root,
            text=(
                "Podés usar la versión DEMO con funcionalidad limitada\n"
                "o activar la versión completa con tu código de licencia."
            ),
            font=("", 9),
            fg="#444444",
            bg="#ffffff",
            justify="center"
        ).pack(pady=(14, 18))

        # ── Botones ───────────────────────────────────────────
        btn_frame = tk.Frame(self.root, bg="#ffffff")
        btn_frame.pack(pady=(0, 20))

        # Botón principal — Continuar en DEMO
        tk.Button(
            btn_frame,
            text="Continuar en DEMO",
            font=("", 10),
            fg="#1a73e8",
            bg="#ffffff",
            activeforeground="#1a73e8",
            activebackground="#f0f4ff",
            relief="solid",
            bd=1,
            cursor="hand2",
            padx=18,
            pady=8,
            command=self._choose_demo
        ).grid(row=0, column=0, padx=8)

        # Botón secundario — Ya tengo licencia
        tk.Button(
            btn_frame,
            text="✓  Activar con mi código",
            font=("", 10, "bold"),
            fg="#ffffff",
            bg="#1a73e8",
            activeforeground="#ffffff",
            activebackground="#1558b0",
            relief="flat",
            cursor="hand2",
            padx=18,
            pady=8,
            command=self._choose_activate
        ).grid(row=0, column=1, padx=8)

        # ── Nota inferior ─────────────────────────────────────
        tk.Label(
            self.root,
            text="Podés activar tu licencia en cualquier momento desde Menú → Licencia",
            font=("", 8),
            fg="#999999",
            bg="#ffffff"
        ).pack(pady=(0, 14))

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _choose_demo(self):
        WelcomeWindow.choice = "demo"
        self.root.destroy()

    def _choose_activate(self):
        WelcomeWindow.choice = "activate"
        self.root.destroy()

    def _on_close(self):
        # Si cierra con la X, equivale a elegir DEMO
        self._choose_demo()

    def _center(self, w, h):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x  = (sw - w) // 2
        y  = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ── Ejecución ─────────────────────────────────────────────────────────────

    def run(self):
        self.root.mainloop()
        return WelcomeWindow.choice


# Alias para compatibilidad con el import existente en check_license.py
ActivationWindow = WelcomeWindow
