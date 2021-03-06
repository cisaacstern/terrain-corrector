import logging

import param
import panel as pn

import terrain.config as c
from terrain.topo import Topography
from terrain.time import TimeSeries
from terrain.params import Correction, Horizon
from terrain.plot import plot_grids, generate_titles, plot_sun

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class Interact(param.Parameterized):
    '''
    A paramaterized classed in the mold of Panel example.
    '''
    def __init__(self, axis_color, canvas_color):
        super(Interact, self).__init__()
        self.axis_color = axis_color
        self.canvas_color = canvas_color
        self._init_config()

    #---parameters---#
    nums = list(c.DATE_DICT.values()) #update this
    date = param.Selector(default=70, objects=nums)
    resolution = param.Integer(30, bounds=(10, 300), step=10)
    sigma = param.Number(1.0, bounds=(0.0, 3.0))
    bins = param.Integer(32, bounds=(8,64), step=8)

    #---helper parameters---#
    time = param.Integer(5, bounds=(0,100)) #needs regen each time

    #---"previous" param values---#
    prev_date = 100
    prev_bin_count = 100
    prev_bin = 100
    prev_time = 5

    #---------------------------------------------------------------------
    # Config
    #---------------------------------------------------------------------
    def _init_config(self):
        self.current_config = {
            'Date': self.date,
            'Res': self.resolution,
            'Sigma': self.sigma,
            'Bins': self.bins,
            'Constants':{
                'Bounds': {
                    'East': c.EAST_BOUNDS,
                    'North': c.NORTH_BOUNDS, 
                    'Elev': c.ELEV_BOUNDS
                },
                'Proj': c.PROJECTION,
                'UTC_Off': c.UTC_OFFSET,
                'Lat_Long': c.LAT_LONG,
                'Time_Res': c.TIME_RESOLUTION,
            },
        }

    @param.depends('date', 'resolution', 'sigma', 'bins')
    def update_config(self):
        '''

        '''
        self.current_config['Date'] = self.date
        self.current_config['Res'] = self.resolution
        self.current_config['Sigma'] = self.sigma
        self.current_config['Bins'] = self.bins
        logger.info('Interact: current_config updated to %s ', self.current_config)

    def return_config(self):
        '''

        '''
        return self.current_config

    #---------------------------------------------------------------------
    # Terrain: Setter & Viewer
    #---------------------------------------------------------------------
    @param.depends('date', 'resolution', 'sigma')
    def set_terrain(self):
        '''
        Instance method for resetting key attributes.
        Note that though this is called from within self.view_grids(),
        it deliberately sets instance variables.
        '''
        self.fname = c.TOPO_LIST[self.date]
        self.params = {'R':self.resolution, 'S':self.sigma, 'B':self.bins}
        logger.debug('Params are %s ', self.params)

        test = Topography(self.fname)
        logger.debug('Topography class was instantiated with fname %s ', self.fname)

        self.grids = test.return_grids(self.params['R'], self.params['S'])

    @param.depends('date', 'resolution', 'sigma')#, 'time')
    def view_terrain(self, view_fn=plot_grids):
        '''
        Two key functions here: (a) sets view attributes; and (b) serves
        the grid plot. dims are variablized because that depends.
        '''

        titles = generate_titles(fn=self.fname, params=self.params, _type='topo')
        cmaps = ['viridis', 'YlOrBr', 'hsv']
        dims = {'figsize':(12,5), 'dpi':80, 'wspace':0.05, 'hspace':0, 
                'left':0.05, 'right':0.97, 'top':0.79, 'bottom':0.1}

        return view_fn(grids=self.grids, params=self.params, titles=titles, 
                        cmaps=cmaps, d=dims, axis_color=self.axis_color, 
                        canvas_color=self.canvas_color)

    #---------------------------------------------------------------------
    # Sun: Setter & Viewer
    #---------------------------------------------------------------------

    @param.depends('date', 'bins')
    def set_sun(self):
        '''

        '''
        def _update_bins_and_dict(dataframe):
            '''

            '''
            self.prev_bin_count = self.bins
            self.df = TimeSeries.reassign_bins(self.bins, dataframe)
            self._dict = TimeSeries.generate_angle_dict(self.bins)

        logger.debug('prev_date and date are %s and %s', 
                    self.prev_date, self.date)

        logger.debug('prev_bin_count and bins are %s and %s', 
                    self.prev_bin_count, self.bins)

        if self.date == self.prev_date:
            logger.debug('Previous and current dates equal. Base df unchanged.')
            if self.prev_bin_count != self.bins:
                logger.debug('Bins were changed. Reassigning bins in df.')
                _update_bins_and_dict(dataframe=self.df)
        else:
            logger.debug('Date was changed. Re-initializing dataframe.')
            self.prev_date = self.date
            ts = TimeSeries(self.date)
            _update_bins_and_dict(dataframe=ts.df)
        

    @param.depends('date', 'bins', 'time')
    def view_sun(self, view_fn=plot_sun):
        '''

        '''
        dims = {'figsize':(4,5), 'dpi':80, 'top':1, 'bottom':0, 
                'left':0.2, 'right':0.95}

        return view_fn(df=self.df, angle_dict=self._dict, time=self.time, 
                        bins=self.bins, d=dims, canvas_color=self.canvas_color, 
                        axis_color=self.axis_color)

    #---------------------------------------------------------------------
    # Correction: Setter & Viewer
    #---------------------------------------------------------------------

    @param.depends('date', 'resolution', 'sigma', 'bins', 'time')#'obscure', 
    def set_horizons(self):
        '''

        For more information on these algorithms, see docstrings in source.
        '''
        self.time_bin = self.df['bin_assignment'].iloc[self.time]

        logger.debug('prev_bin and time_bin are %s and %s', 
                    self.prev_bin, self.time_bin)

        if self.time_bin == self.prev_bin:
            logger.debug('Previous and current time_bin equal. No update made.')
            pass
        else:
            self.prev_bin = self.time_bin
            logger.debug('Update: time_bin was reset to %s ', self.time_bin)
            self.azi = self._dict[self.time_bin]
            elev_grid, _, _ = self.grids
            horz = Horizon(df=self.df, azimuth=self.azi, elev_grid=elev_grid)
            self.rot_elev = horz.rotated_elevation_grid
            self.rot_slope = horz.rotated_slope_array

    @param.depends('date', 'resolution', 'sigma', 'bins', 'time')#'obscure',
    def set_correction(self):

        slope_and_aspect_grids = self.grids[1:]
        self.corr_array = Correction.calculate_correction(
            grids=slope_and_aspect_grids, 
            df=self.df,
            time=self.time
        )

        # start working area

        alt = self.df['solar_altitude'].iloc[self.time]
        self.mask = Horizon.calc_obstruction_for_altitude(
            altitude=alt, azimuth=self.azi, 
            rot_elev=self.rot_elev, rot_slope=self.rot_slope,
            resolution=self.params['R']
        )
        # end working area

            
    @param.depends('date', 'resolution', 'sigma', 'bins', 'time')#'obscure', 
    def view_correction(self, view_fn=plot_grids):
        '''
        
        '''

        titles = generate_titles(fn=self.fname, params=self.params, _type='time')
        cmaps = ['magma', 'binary']
        dims = {'figsize':(8,5), 'dpi':80, 'wspace':0.1, 'hspace':0, 
                'left':0.05, 'right':0.97, 'top':0.79, 'bottom':0.1}

        # corr_horizon_array = corr.calculate_horizons
        grids = [self.corr_array, self.mask] 
        return view_fn(grids=grids, params=self.params, titles=titles, 
                        cmaps=cmaps, d=dims, axis_color=self.axis_color, 
                        canvas_color=self.canvas_color)

    #---------------------------------------------------------------------
    # Model runner
    #---------------------------------------------------------------------

    def run_model(self):
        # can i call the same functions?
        pass