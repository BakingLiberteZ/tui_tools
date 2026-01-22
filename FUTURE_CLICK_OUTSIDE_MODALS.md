# 🔮 Mejora Futura: Cerrar Modales con Click Fuera

## 🎯 Solicitud del Usuario

> "Cuando se abre un modal, el que sea, cuando le doy click fuera del modal, debe salir de ese modal, no quedarse allí."

---

## 📊 Estado Actual

### Formas de Cerrar Modales:

✅ **Actualmente implementado:**
- Click en botones: Cancel, Done, Close, No
- Tecla **Escape** (implementado en la mayoría de modales)

❌ **No implementado:**
- Click fuera del modal (en el overlay/fondo)

---

## 🔧 Implementación Requerida

### Solución Técnica:

Para cerrar modales al hacer click fuera, se necesita agregar un handler en cada clase de modal que:

1. Detecte eventos de click
2. Verifique si el click fue en el overlay (fondo) y no en el contenedor del modal
3. Llame a `self.dismiss()` para cerrar el modal

### Código Ejemplo:

```python
class MyModalScreen(ModalScreen[str]):
    # ... CSS y otros métodos ...

    def on_click(self, event: Click) -> None:
        """Close modal when clicking outside the modal content."""
        # Verificar si el click fue en el propio ModalScreen (overlay)
        # y no en un widget hijo (contenido del modal)
        if event.widget == self:
            self.dismiss(None)  # Cerrar el modal
```

### Aplicar a Todos los Modales:

Este código debe agregarse a cada una de las clases de modales:

1. **PromptScreen** - Base para inputs (Import, SEND amount/passphrase)
2. **SendAmountScreen** - Hereda de PromptScreen
3. **SendPassphraseScreen** - Hereda de PromptScreen
4. **ConfirmScreen** - Confirmaciones (Delete)
5. **NetworkPickerScreen** - Selector de red
6. **ReceiveScreen** - Mostrar dirección
7. **AddressDetailScreen** - Detalles de dirección
8. **WalletSelectorScreen** - Base para selectores
9. **BackupWalletSelectorScreen** - Hereda de WalletSelectorScreen
10. **ExportWalletSelectorScreen** - Hereda de WalletSelectorScreen
11. **DestinationPickerScreen** - Selector de destino (SEND)
12. **ConfirmSendScreen** - Confirmación de envío
13. **TxDetailsScreen** - Detalles de transacción

**Total: ~13 clases de modales**

---

## 🎨 Alternativa: Clase Base

Para evitar duplicación de código, se podría crear una clase base:

```python
class DismissibleModalScreen(ModalScreen[T]):
    """ModalScreen that can be dismissed by clicking outside."""

    def on_click(self, event: Click) -> None:
        """Close modal when clicking outside the modal content."""
        if event.widget == self:
            self.dismiss(None)

# Luego heredar de esta clase:
class PromptScreen(DismissibleModalScreen[str]):
    # ... resto del código ...
```

**Ventaja**: Solo agregar el handler una vez
**Desventaja**: Requiere cambiar la herencia de todas las clases de modales

---

## ⚠️ Consideraciones

### 1. **Modales de Confirmación Críticos**

Algunos modales no deberían cerrarse con click accidental fuera:
- **Delete Wallet** (ConfirmScreen) - Acción destructiva
- **Confirm Send** (ConfirmSendScreen) - Transacción con fondos

Para estos casos, se puede:
- No implementar el click-fuera
- O requerir confirmación adicional

### 2. **Consistency con Escape**

Si se implementa click-fuera, debe comportarse igual que Escape:
- Ambos deben cancelar la acción
- Ambos deben retornar el mismo valor (None o False)

### 3. **UX en Terminales**

En algunos terminales, el manejo de clicks puede ser diferente. Debe probarse en:
- Terminal nativo de Linux
- Terminal de macOS
- Windows Terminal
- tmux/screen

---

## 📊 Prioridad

**Nivel**: Media

**Beneficios**:
- ✅ UX más intuitiva (comportamiento estándar en UI modernas)
- ✅ Forma rápida de cerrar modales sin buscar el botón
- ✅ Consistente con aplicaciones GUI

**Costos**:
- ⚠️ Requiere modificar ~13 clases de modales
- ⚠️ Posible riesgo de cerrar accidentalmente modales críticos
- ⚠️ Necesita pruebas en diferentes terminales

---

## 🚀 Plan de Implementación

### Fase 1: Modales Simples (Bajo Riesgo)

Implementar click-fuera en modales que no tienen acciones críticas:

1. **ReceiveScreen** - Solo muestra información
2. **AddressDetailScreen** - Solo muestra información
3. **TxDetailsScreen** - Solo muestra información
4. **NetworkPickerScreen** - Selección reversible

### Fase 2: Modales de Input (Riesgo Medio)

Implementar en modales de input donde Escape ya funciona:

5. **PromptScreen** (y sus herederas: SendAmountScreen, SendPassphraseScreen)
6. **WalletSelectorScreen** (y sus herederas: Backup, Export)
7. **DestinationPickerScreen**

### Fase 3: Evaluación de Modales Críticos

Decidir caso por caso:

8. **ConfirmScreen** (Delete) - ¿Permitir click-fuera?
9. **ConfirmSendScreen** - ¿Permitir click-fuera?

**Recomendación**: NO implementar en modales críticos, o agregar confirmación adicional.

---

## 🧪 Testing Requerido

Si se implementa, debe probarse:

1. **Click en overlay** → Modal se cierra
2. **Click en contenido del modal** → Modal NO se cierra
3. **Click en botones** → Modal se cierra/confirma apropiadamente
4. **Tecla Escape** → Sigue funcionando igual
5. **Diferentes terminales** → Comportamiento consistente

---

## 📝 Estado

**Actual**: ❌ No implementado

**Workaround**: Los usuarios pueden usar:
- Tecla **Escape** (rápido y universal)
- Botones **Cancel** / **Done** / **Close**

**Implementación futura**: Pendiente según prioridad del proyecto

---

## 💡 Recomendación

### Implementar en Fases:

1. **Corto plazo**: Asegurar que TODOS los modales respondan a Escape (algunos ya lo tienen)
2. **Mediano plazo**: Implementar click-fuera en modales simples (Fase 1)
3. **Largo plazo**: Evaluar implementación en modales de input (Fase 2)
4. **A considerar**: Decidir política para modales críticos (Fase 3)

### Alternativa Inmediata:

Si no se implementa click-fuera, se puede:
- Documentar claramente que Escape cierra modales
- Agregar hint visual en modales: "[dim]Escape to close[/dim]"
- Asegurar que todos los botones Cancel estén siempre visibles

---

**Fecha**: $(date)
**Tipo**: Future Enhancement
**Complejidad**: Media (~13 clases a modificar)
**Prioridad**: Media (mejora de UX, no crítica)
**Estado**: 📋 Pendiente
