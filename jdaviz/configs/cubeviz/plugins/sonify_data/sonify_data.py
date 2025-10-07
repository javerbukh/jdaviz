from traitlets import Bool, List, Unicode, observe
import astropy.units as u
import os
from io import BytesIO

from jdaviz.core.events import ViewerAddedMessage, GlobalDisplayUnitChanged
from base64 import b64encode
from jdaviz.core.custom_traitlets import IntHandleEmpty, FloatHandleEmpty
from jdaviz.core.registries import tray_registry
from jdaviz.core.template_mixin import (
    PluginTemplateMixin,
    DatasetSelectMixin,
    SpectralSubsetSelectMixin,
    with_spinner,
    AddResultsMixin,
    ViewerSelectMixin,
)
from jdaviz.core.user_api import PluginUserApi


__all__ = ["SonifyData"]

try:
    import strauss # noqa
    from scipy.io.wavfile import write as write_wav
    _has_strauss = True
except ImportError:
    _has_strauss = False
try:
    import sounddevice as sd
except (ImportError, OSError):

    class Empty:
        pass

    sd = Empty()
    sd.default = Empty()
    sd.default.device = [-1, -1]
    sd.query_devices = lambda: []
    
# TODO: create this directory for stock sounds?
SOUND_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "data", "sounds"
)


@tray_registry("cubeviz-sonify-data", label="Sonify Data")
class SonifyData(
        PluginTemplateMixin, DatasetSelectMixin, SpectralSubsetSelectMixin, AddResultsMixin, ViewerSelectMixin 
):
    """
    See the :ref:`Sonify Data Plugin Documentation <cubeviz-sonify-data>` for more details.

    Only the following attributes and methods are available through the
    :ref:`public plugin API <plugin-apis>`:

    * :meth:`~jdaviz.core.template_mixin.PluginTemplateMixin.show`
    * :meth:`~jdaviz.core.template_mixin.PluginTemplateMixin.open_in_tray`
    * :meth:`~jdaviz.core.template_mixin.PluginTemplateMixin.close_in_tray`
    """

    template_file = __file__, "sonify_data.vue"

    # Removing UI option to vary these for now
    sample_rate = IntHandleEmpty(44100).tag(sync=True)
    buffer_size = 2048  # IntHandleEmpty(2048).tag(sync=True)
    assidx = FloatHandleEmpty(2.5).tag(sync=True)
    ssvidx = FloatHandleEmpty(0.65).tag(sync=True)
    eln = Bool(True).tag(sync=True)
    audfrqmin = FloatHandleEmpty(50).tag(sync=True)
    audfrqmax = FloatHandleEmpty(1000).tag(sync=True)
    use_pccut = Bool(True).tag(sync=True)
    pccut = IntHandleEmpty(20).tag(sync=True)
    volume = IntHandleEmpty(100).tag(sync=True)
    stream_active = Bool(True).tag(sync=True)
    has_strauss = Bool(_has_strauss).tag(sync=True)
    has_outs = Bool((sd.default.device[1] != -1)).tag(sync=True)
    scrubdx = IntHandleEmpty(0).tag(sync=True)
    
    # TODO: can we refresh the list, so sounddevices are up-to-date when dropdown clicked?
    sound_devices_items = List().tag(sync=True)
    sound_devices_selected = Unicode("").tag(sync=True)

    add_to_viewer_enabled = Bool(False).tag(sync=True)

    # SFX
    sound_in = Unicode("").tag(sync=True)
    sound_out = Unicode("").tag(sync=True)
    on_audio_data = Unicode("").tag(sync=True)
    cube_audio_data = Unicode("").tag(sync=True)
    
    # some addiional attributes for JS
    first_sonification_done = Bool(False).tag(sync=True)
    thisfile = Unicode(SOUND_DIR).tag(sync=True)
    x_pos = IntHandleEmpty(-1).tag(sync=True)
    y_pos = IntHandleEmpty(-1).tag(sync=True)
    lindx = IntHandleEmpty(-1).tag(sync=True)
    nsamps = IntHandleEmpty(-1).tag(sync=True)
    npix = IntHandleEmpty(-1).tag(sync=True)
    nsecs = FloatHandleEmpty(-1).tag(sync=True)
    is_playing = Bool(False).tag(sync=True)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._plugin_description = "Sonify a data cube"
        self.docs_description = "Sonify a data cube using the Strauss package."
        if not self.has_strauss:
            self.disabled_msg = (
                "To use Sonify Data, install strauss and restart Jdaviz. You "
                "can do this by running pip install strauss in the command"
                " line and then launching Jdaviz. Currently, this plugin only"
                " works on devices with valid sound output."
            )

        else:
            self.sound_device_indexes = None
            self.refresh_device_list()

        self.results_label_default = "Sonified data"
        self.add_to_viewer_selected = "flux-viewer"

    def _on_viewer_added(self, msg):
        # TODO 
        pass
    
    def _create_viewer_callbacks(self, viewer):
        mm_callback = self._viewer_callback(viewer, self._on_viewer_mouse_move)
        me_callback = self._viewer_callback(viewer, self._on_viewer_mouse_enter)
        ml_callback = self._viewer_callback(viewer, self._on_viewer_mouse_leave)
        viewer.add_event_callback(mm_callback, events=['mousemove'])
        viewer.add_event_callback(me_callback, events=['mouseenter'])
        viewer.add_event_callback(ml_callback, events=['mouseleave'])
                        
    def _on_viewer_mouse_move(self, viewer, data):
        if data['event'] == 'mousemove':
            pixel_data = self.coords_info.as_dict()
            self.x_pos, self.y_pos = int(pixel_data['axes_x']), int(pixel_data['axes_y'])
            self.lindx = int(self.x_pos*self.flux_viewer.sonified_cube.sigcube.shape[1] + self.y_pos)

    def _on_viewer_mouse_enter(self, viewer, data):
        if data['event'] == 'mouseenter':
            print('in')
            self.is_playing = True
            
    def _on_viewer_mouse_leave(self, viewer, data):
        if data['event'] == 'mouseleave':
            print('out')
            self.is_playing = False
            
    @property
    def coords_info(self):
        return self.app.session.application._tools['g-coords-info']
    
    @property
    def user_api(self):
        expose = ["sonify_cube", "lindx", "x_pos", "y_pos",
                  "nsamps", "nsecs", "sample_rate", "is_playing"]
        return PluginUserApi(self, expose)

    def sonify_cube(self):
        """
        Create a sonified grid in the flux viewer so that sound plays when mousing over the viewer.
        You can select the device index for audio output and also use a spectral subset to set a
        range for sonification.
        """
        if self.disabled_msg:
            raise ValueError("Unable to sonify cube")

        # Get index of selected device
        if self.sound_devices_selected:
            selected_device_index = self.sound_device_indexes[
                self.sound_devices_selected
            ]
        else:
            selected_device_index = None

        # Apply spectral subset bounds
        if self.spectral_subset_selected != self.spectral_subset.default_text:
            display_unit = self.spectrum_viewer.state.x_display_unit
            min_wavelength = self.spectral_subset.selected_obj.lower.to_value(
                u.Unit(display_unit)
            )
            max_wavelength = self.spectral_subset.selected_obj.upper.to_value(
                u.Unit(display_unit)
            )
            self.flux_viewer.update_listener_wls(
                (min_wavelength, max_wavelength), display_unit
            )

        # Ensure the current spectral region bounds are up-to-date at render time
        self.update_wavelength_range(None)
        # generate the sonified cube
        self.flux_viewer.get_sonified_cube(
            self.sample_rate,
            self.buffer_size,
            selected_device_index,
            self.assidx,
            self.ssvidx,
            self.pccut,
            self.audfrqmin,
            self.audfrqmax,
            self.eln,
            self.use_pccut,
            self.results_label,
        )

        self.nsamps = self.flux_viewer.sonified_cube.sigcube.shape[-1]
        self.npix = self.flux_viewer.sonified_cube.sigcube[:,:,0].size
        self.nsecs = self.flux_viewer.sonified_cube.sigcube.shape[-1]/self.sample_rate
        
        # lets create a callback to follow the flux-viewer mouse positions
        self._create_viewer_callbacks(self.app.get_viewer('flux-viewer'))


        wholecube = (self.flux_viewer.sonified_cube.sigcube).flatten()
        print(wholecube.max(), wholecube.dtype)
        cube_buffer = BytesIO()
        write_wav(
            cube_buffer,
            self.sample_rate,
            wholecube,
        )
        cube_buffer.seek(0)
        self.cube_audio_data = b64encode(cube_buffer.read()).decode("utf-8")
        
        # In-memory WAV file
        on_buffer = BytesIO()
        write_wav(
            on_buffer,
            self.sample_rate,
            self.flux_viewer.sonified_cube.notification_sounds["on"].astype("int16"),
        )
        on_buffer.seek(0)

        self.on_audio_data = b64encode(on_buffer.read()).decode("utf-8")
        self.first_sonification_done = True
        
    @with_spinner()
    def vue_sonify_cube(self, *args):
        self.sonify_cube()
        
    def vue_start_stop_stream(self, *args):
        self.stream_active = not self.stream_active
        self.flux_viewer.stream_active = not self.flux_viewer.stream_active

    @observe("spectral_subset_selected")
    def update_wavelength_range(self, event):
        if not hasattr(self, "spectral_subset"):
            return
        display_unit = self.spectrum_viewer.state.x_display_unit
        # is this spectral selection or the entire spectrum?
        if hasattr(self.spectral_subset.selected_obj, "subregions"):
            wlranges = self.spectral_subset.selected_obj.subregions
        else:
            wlranges = None
            self.flux_viewer.update_listener_wls(wlranges, display_unit)

    @observe("volume")
    def update_volume_level(self, event):
        self.flux_viewer.update_volume_level(event["new"])

    @observe("sound_devices_selected")
    def update_sound_device(self, event):
        if event["new"] != event["old"]:
            didx = dict(zip(*self.build_device_lists()))[event["new"]]
            self.flux_viewer.update_sound_device(didx)

    def refresh_device_list(self):
        devices, indexes = self.build_device_lists()
        self.sound_device_indexes = dict(zip(devices, indexes))
        self.sound_devices_items = devices
        if len(devices) > 0:
            self.sound_devices_selected = dict(zip(indexes, devices))[
                sd.default.device[1]
            ]
        else:
            self.sound_devices_selected = ""

    def vue_refresh_device_list_in_dropdown(self, *args):
        self.refresh_device_list()

    def build_device_lists(self):
        # dedicated function to build the current *output*
        # device and index lists
        devices = []
        device_indexes = []
        for index, device in enumerate(sd.query_devices()):
            if device["max_output_channels"] > 0 and device["name"] not in devices:
                devices.append(device["name"])
                device_indexes.append(index)
        return devices, device_indexes
