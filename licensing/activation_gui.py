
import tkinter as tk
from tkinter import messagebox

from .hardware_id import get_hardware_id
from .license_manager import activate_license


class ActivationWindow:

    def __init__(self):

        self.root = tk.Tk()
        self.root.title("Activación de licencia")

        tk.Label(self.root, text="Hardware ID").pack()

        hw = get_hardware_id()

        self.hw_entry = tk.Entry(self.root, width=60)
        self.hw_entry.pack()
        self.hw_entry.insert(0, hw)

        tk.Label(self.root, text="Ingrese licencia").pack()

        self.license_entry = tk.Entry(self.root, width=40)
        self.license_entry.pack()

        tk.Button(self.root, text="Activar", command=self.activate).pack(pady=10)

    def activate(self):

        key = self.license_entry.get()

        try:

            activate_license(key)

            messagebox.showinfo("Licencia", "Activación correcta")

            self.root.destroy()

        except Exception as e:

            messagebox.showerror("Error", str(e))

    def run(self):

        self.root.mainloop()
